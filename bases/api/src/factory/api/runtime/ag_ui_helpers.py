"""AG-UI message mapping + SSE formatting helpers.

Extracted from ``ag_ui_routes.py`` so that file stays a thin transport
shell under the 200 LOC budget. Helpers here:

- ``extract_user_message``: pull the latest user message out of the request
- ``unwrap_agent_output``: pull prose out of a typed ``ToolResult`` envelope
- ``extract_ag_ui_events``: map an ``agent_reason`` result to AG-UI events
- ``execute_tool_calls``: invoke any tool_calls returned by the agent and
  emit AG-UI ``TOOL_CALL_START``/``TOOL_CALL_END`` events
- ``sse``: format a dict as an SSE ``data:`` line
- ``error_response``: build a 400 JSON response for bad requests
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Bubbled to users verbatim when a run fails; never a raw envelope repr.
TOOL_FALLBACK_TEXT = (
    "I hit an internal error while working on that. Please try again."
)


def extract_user_message(messages: list[dict]) -> str:
    """Return the most recent user message from a messages array.

    AG-UI clients send the user turn as content blocks
    (``[{"type": "text", "text": "..."}]``), not a bare string; collapse
    to plain text so the typed ``ReasonInput(task: str)`` validates.
    Mirrors ``content_text`` in the agent's langchain_stream adapter.
    """
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    block["text"] for block in content
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                )
            return str(content)
    return ""


def extract_user_message_id(messages: list[dict]) -> str | None:
    """Return the latest user message's standard AG-UI id when present."""
    for message in reversed(messages):
        if message.get("role") == "user":
            value = message.get("id")
            return value if isinstance(value, str) and value else None
    return None


def unwrap_agent_output(agent_result: Any) -> str | None:
    """Return the assistant prose inside an ``agent_reason`` result.

    Navigates the nested typed-MCP envelope (``data.result.output`` and
    friends) instead of stringifying the whole envelope. Returns ``None``
    for failed envelopes so callers can emit a graceful fallback rather
    than a raw Python repr as the chat reply.
    """
    if isinstance(agent_result, str):
        return agent_result or None
    if not isinstance(agent_result, dict):
        return str(agent_result) if agent_result else None
    if agent_result.get("ok") is False:
        return None
    data = agent_result.get("data")
    candidates: list[Any] = [
        agent_result.get("text"),
        agent_result.get("output"),
        agent_result.get("result"),
        data.get("output") if isinstance(data, dict) else None,
        data.get("result") if isinstance(data, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        if isinstance(candidate, dict):
            nested = candidate.get("output", candidate.get("text", ""))
            if isinstance(nested, str) and nested.strip():
                return nested
    return None


def extract_ag_ui_events(
    agent_result: Any, thread_id: str,
) -> list[dict[str, Any]]:
    """Map an ``agent_reason`` result to AG-UI ``TEXT_MESSAGE_*`` events."""
    ts = time.time()
    msg_id = str(uuid.uuid4())[:8]
    text = unwrap_agent_output(agent_result)
    if text is None:
        if isinstance(agent_result, dict) and agent_result.get("ok") is False:
            # A failed typed envelope must never surface as chat text —
            # emit a graceful fallback so the UI shows prose, not a repr.
            logger.error(
                "agent_reason returned a failed envelope thread_id=%s error=%s",
                thread_id, agent_result.get("error"),
            )
            text = TOOL_FALLBACK_TEXT
        else:
            return []
    if not text:
        return []
    return [
        {"type": "TEXT_MESSAGE_START", "messageId": msg_id,
         "role": "assistant", "timestamp": ts},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id,
         "delta": text, "timestamp": ts},
        {"type": "TEXT_MESSAGE_END", "messageId": msg_id, "timestamp": ts},
    ]


async def execute_tool_calls(
    agent_result: dict,
    call_tool: Callable[[str, dict], Awaitable[Any]],
) -> list[dict[str, Any]]:
    """Run any ``tool_calls`` from ``agent_result``, returning AG-UI events.

    ``call_tool`` is injected so this helper has no compile-time dependency
    on the API base's bridge module.
    """
    tool_calls = agent_result.get("tool_calls", [])
    if not tool_calls:
        return []
    events: list[dict] = []
    for tc in tool_calls:
        name = tc.get("tool") or tc.get("name", "unknown")
        args = tc.get("arguments", tc.get("args", {}))
        tc_id = tc.get("id", str(uuid.uuid4())[:8])
        events.append({"type": "TOOL_CALL_START", "toolCallId": tc_id,
                       "toolCallName": name, "timestamp": time.time()})
        try:
            result = await call_tool(name, args if isinstance(args, dict) else {})
            payload = json.dumps(result) if result else "null"
        except Exception as exc:
            payload = json.dumps({"error": str(exc)})
        events.append({"type": "TOOL_CALL_END", "toolCallId": tc_id,
                       "result": payload, "timestamp": time.time()})
    return events


def sse(event: dict[str, Any]) -> str:
    """Format a dict as an SSE ``data:`` line."""
    return f"data: {json.dumps(event)}\n\n"


def error_response(message: str):
    """Return a 400 JSON response for bad requests."""
    from starlette.responses import JSONResponse
    return JSONResponse(status_code=400, content={"detail": message})
