"""Strands event-stream → ChatStreamEvent translation.

``Agent.stream_async`` yields dicts. The ones carrying chat semantics:

- ``{"data", "delta", ...}`` — TextStreamEvent / ToolUseStreamEvent
  (callback events; text and tool-arg accumulation).
- ``{"message": <assistant Message>}`` — ModelMessageEvent: the final
  assistant message. Text here is already streamed via ``data``, so only
  the whole tool-use blocks are lifted (Strands accumulates tool input
  client-side — ``current_tool_use`` grows per delta — rather than
  emitting index-keyed provider deltas; the completed block with its
  stable ``toolUseId`` is the one reliable emission point).
- ``{"message": <user Message with toolResult blocks>}`` —
  ToolResultMessageEvent: ``ToolResultEvent`` itself is never surfaced
  to ``stream_async`` consumers (``is_callback_event == False``), so
  the formatted user message is where tool results are observed.
- ``{"result": AgentResult}`` — terminal, carries ``stop_reason``.

The structured-payload unwrap mirrors ``langchain_stream._structured_payload``:
MCP paint envelopes ride ``CallToolResult``-shaped dicts and must reach the
AG-UI mapper as structured JSON, not escaped text.
"""
from __future__ import annotations

import json
from typing import Any

_DONE_REASONS = {
    "end_turn": "stop", "stop_sequence": "stop", "cancelled": "stop",
    # Interrupted runs surface the pending frontend payload as a
    # tool_result first; the turn itself is a clean stop for the UI.
    "interrupt": "stop",
    "tool_use": "tool_use", "max_tokens": "max_tokens",
    "limit_output_tokens": "max_tokens",
}


def structured_payload(content: Any) -> Any:
    """Prefer MCP ``structured_content`` over the escaped text block."""
    if isinstance(content, (str, bytes)):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return content
    if isinstance(content, list):
        texts = [
            block.get("text") for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if len(content) == 1 and texts and texts[0] is not None:
            return structured_payload(texts[0])
        return content
    if not isinstance(content, dict):
        return content
    structured = content.get("structured_content")
    if structured is not None:
        return structured
    inner = content.get("content")
    if isinstance(inner, list):
        return structured_payload(inner)
    return content


def strands_event_tuples(event: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Translate one raw ``stream_async`` event dict into union tuples."""
    if "result" in event:
        result = event["result"]
        reason = str(getattr(result, "stop_reason", "end_turn"))
        return [("done", {"reason": _DONE_REASONS.get(reason, "stop")})]
    if "message" in event:
        return _message_tuples(event["message"])
    if "delta" in event and isinstance(event.get("delta"), dict):
        return _delta_tuples(event)
    if "force_stop" in event:
        return [("error", {"message": str(event.get("force_stop_reason", "forced stop"))})]
    return []


def _delta_tuples(event: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    delta = event["delta"]
    events: list[tuple[str, dict[str, Any]]] = []
    if "text" in delta:
        events.append(("text_delta", {"content": delta["text"], "message_id": "strands"}))
    reasoning = delta.get("reasoningContent") or {}
    if isinstance(reasoning, dict) and reasoning.get("text"):
        events.append(("reasoning_text", {"content": reasoning["text"]}))
    return events


def _message_tuples(message: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(message, dict):
        return []
    events: list[tuple[str, dict[str, Any]]] = []
    if message.get("role") == "assistant":
        for block in message.get("content", ()):
            if isinstance(block, dict) and isinstance(block.get("toolUse"), dict):
                tool_use = block["toolUse"]
                events.append(("tool_call_delta", {
                    "tool_call_id": str(tool_use.get("toolUseId", "")),
                    "tool_name": tool_use.get("name"),
                    "args_delta": json.dumps(tool_use.get("input", {})),
                }))
    elif message.get("role") == "user":
        for block in message.get("content", ()):
            if not isinstance(block, dict) or not isinstance(block.get("toolResult"), dict):
                continue
            tool_result = block["toolResult"]
            content = structured_payload(tool_result.get("content"))
            events.append(("tool_result", {
                "tool_call_id": str(tool_result.get("toolUseId", "")),
                "payload": content,
                "is_error": tool_result.get("status") == "error",
            }))
    return events


__all__ = ["strands_event_tuples", "structured_payload"]
