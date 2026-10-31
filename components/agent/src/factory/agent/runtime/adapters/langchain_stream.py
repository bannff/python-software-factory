"""LangGraph stream input, resume, and message normalization helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolChunkState:
    """Correlate provider continuation chunks by LangChain tool index."""

    ids: dict[int, str] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)
    last_index: int = 0


async def graph_input(graph: Any, config: dict[str, Any], request: Any) -> Any:
    """Return a new user turn or a native resume command for pending interrupts."""
    snapshot = await graph.aget_state(config)
    interrupts = tuple(snapshot.interrupts)
    if not interrupts:
        return {"messages": [{"role": "user", "content": request.prompt}]}
    replies = _tool_replies(request.messages)
    resume: dict[str, Any] = {}
    for item in interrupts:
        payload = item.value if isinstance(item.value, dict) else {}
        tool_call_id = str(payload.get("tool_call_id") or "")
        if tool_call_id not in replies:
            raise ValueError(f"missing frontend tool result for {tool_call_id or item.id}")
        resume[item.id] = replies[tool_call_id]
    from langgraph.types import Command

    return Command(resume=resume)


def pending_frontend_events(snapshot: Any) -> list[tuple[str, dict[str, Any]]]:
    """Expose paused frontend calls through the existing ToolResultEvent sentinel."""
    events: list[tuple[str, dict[str, Any]]] = []
    for item in snapshot.interrupts:
        payload = item.value
        if not isinstance(payload, dict) or not payload.get("_frontend_pending"):
            continue
        events.append(("tool_result", {
            "tool_call_id": str(payload.get("tool_call_id") or item.id),
            "payload": payload,
            "is_error": False,
        }))
    return events




def pending_approval_events(snapshot: Any) -> list[tuple[str, dict[str, Any]]]:
    """Expose listed-tool pauses through the existing approval-card event rail."""
    events: list[tuple[str, dict[str, Any]]] = []
    for item in snapshot.interrupts:
        payload = item.value
        if not isinstance(payload, dict) or not payload.get("_approval_pending"):
            continue
        events.append(("interrupt", {
            "interrupt_id": str(payload.get("interrupt_id") or item.id),
            "tool": str(payload.get("tool") or "tool"),
            "command": str(payload.get("command") or ""),
        }))
    return events


def pending_interrupt_events(snapshot: Any) -> list[tuple[str, dict[str, Any]]]:
    """Return approval and frontend pauses in one runtime-facing sequence."""
    return [*pending_approval_events(snapshot), *pending_frontend_events(snapshot)]


def _structured_payload(content: Any) -> Any:
    """Prefer MCP ``structured_content`` over the escaped text block.

    ``invoke_capability`` returns ``asdict(CapabilityResult)`` — the
    normalized MCP ``CallToolResult`` shape ``{content: [...],
    structured_content: {...}}``. LangGraph stringifies it into the
    ``ToolMessage`` (or keeps the dict), so a paint-tool envelope only
    reaches the AG-UI stream as JSON-encoded text inside a text block
    and the frontend carrier detectors see no ``components`` / ``ui://``
    at all ("nothing paints"). Unwrap once here so every tool result —
    not just paint — rides the stream as structured JSON.
    """
    if isinstance(content, (str, bytes)):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return content
    if isinstance(content, list):
        # Text-only content-block list (e.g. a CallToolResult.content
        # passthrough): carry the first text block's JSON when present.
        texts = [
            block.get("text") for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if len(content) == 1 and texts and texts[0] is not None:
            return _structured_payload(texts[0])
        return content
    if not isinstance(content, dict):
        return content
    structured = content.get("structured_content")
    if structured is not None:
        return structured
    # CallToolResult.content passthrough without structured_content —
    # recover the payload from a single text block.
    inner = content.get("content")
    if isinstance(inner, list):
        return _structured_payload(inner)
    return content


_CANVAS_TARGETS = frozenset({"graph", "timeline", "findings", "live"})


def _canvas_state_delta(payload: Any) -> tuple[str, str, dict[str, Any]] | None:
    """Extract a ``(target, mode, payload)`` canvas paint from a tool result.

    Port of the Strands ``state_delta_plugin`` (removed in the native-v2
    migration, a4437ac0) to the LangGraph message path: ``ui_paint_canvas``
    returns a v1 envelope whose ``data`` carries the ``_a2ui_canvas``
    sentinel. The AG-UI mapper consumes the resulting ``state_delta`` event
    and emits ``STATE_SNAPSHOT`` / ``STATE_DELTA`` so the canvas views
    (``agentState.canvas.<slot>``) paint. Malformed sentinels return
    ``None`` — never a stream failure.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != "v1":
        return None
    if payload.get("ok") is not True or payload.get("error") is not None:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    sentinel = data.get("_a2ui_canvas")
    if not isinstance(sentinel, dict):
        return None
    target = sentinel.get("target")
    mode = sentinel.get("mode", "snapshot")
    slot_payload = sentinel.get("payload")
    if target not in _CANVAS_TARGETS or mode not in ("snapshot", "delta"):
        return None
    if not isinstance(slot_payload, dict):
        return None
    return str(target), str(mode), slot_payload


def message_events(
    message: Any, state: ToolChunkState | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Translate chunks while correlating provider tool continuations."""
    from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

    chunk_state = state or ToolChunkState()

    events: list[tuple[str, dict[str, Any]]] = []
    message_id = str(getattr(message, "id", "") or "langchain-message")
    content = getattr(message, "content", "")
    text = content_text(content)
    if isinstance(message, (AIMessage, AIMessageChunk)) and text:
        events.append(("text_delta", {"content": text, "message_id": message_id}))
    for chunk in getattr(message, "tool_call_chunks", ()) or ():
        raw_index = chunk.get("index")
        index = raw_index if isinstance(raw_index, int) else chunk_state.last_index
        tool_call_id = str(chunk.get("id") or "")
        tool_name = chunk.get("name")
        if tool_call_id:
            chunk_state.ids[index] = tool_call_id
        if tool_name:
            chunk_state.names[index] = str(tool_name)
        resolved_id = tool_call_id or chunk_state.ids.get(index, "")
        resolved_name = tool_name or chunk_state.names.get(index)
        if not resolved_id:
            continue
        chunk_state.last_index = index
        events.append(("tool_call_delta", {
            "tool_call_id": resolved_id,
            "tool_name": resolved_name,
            "args_delta": chunk.get("args") or "",
        }))
    if isinstance(message, ToolMessage):
        structured = _structured_payload(content)
        payload: dict[str, Any] = {
            "tool_call_id": str(getattr(message, "tool_call_id", "")),
            "payload": structured if structured is not None else content,
            "is_error": getattr(message, "status", "success") == "error",
        }
        events.append(("tool_result", payload))
        paint = _canvas_state_delta(payload["payload"])
        if paint is not None:
            target, mode, slot_payload = paint
            events.append(("state_delta", {
                "target": target, "mode": mode, "payload": slot_payload,
            }))
    return events


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        block["text"] for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )


def last_assistant_text(messages: Any) -> str:
    for message in reversed(list(messages)):
        if getattr(message, "type", "") == "ai" and (text := content_text(message.content)):
            return text
    return ""


def _tool_replies(messages: Any) -> dict[str, Any]:
    replies: dict[str, Any] = {}
    for message in messages or ():
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        tool_call_id = message.get("toolCallId") or message.get("tool_call_id")
        if not tool_call_id:
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError):
                pass
        replies[str(tool_call_id)] = content
    return replies


__all__ = [
    "graph_input", "last_assistant_text", "message_events",
    "pending_approval_events", "pending_frontend_events",
    "pending_interrupt_events",
]
