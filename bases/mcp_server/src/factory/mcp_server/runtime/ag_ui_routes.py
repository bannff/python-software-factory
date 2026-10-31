"""AG-UI SSE endpoint — streams agent execution as AG-UI typed events.

Invokes agent_reason with MCP tool context, executes tool_calls,
maps results to AG-UI events, streams via SSE.

Pure transport shell on the unified MCP server.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from factory.mcp_utils.interface import make_serializable

logger = logging.getLogger(__name__)

# CORS handled globally by Starlette CORSMiddleware (factory.mcp_utils.cors).


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool by name via the aggregator."""
    import asyncio
    from ..core import get_aggregator

    agg = get_aggregator()
    if agg is None:
        return None
    try:
        result = agg.invoke_tool(tool_name, **arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return make_serializable(result)
    except Exception as exc:
        logger.warning("_call_tool(%s) failed: %s", tool_name, exc)
        return None


def _build_tool_context(thread_id: str) -> dict[str, Any]:
    """Build context dict with available MCP tools for the agent."""
    from ..core import get_aggregator

    agg = get_aggregator()
    if agg is None:
        return {"thread_id": thread_id}
    try:
        return {"thread_id": thread_id, "available_tools": agg.get_all_tool_names()}
    except Exception:
        return {"thread_id": thread_id}


def register_ag_ui_routes(app) -> None:
    """Register AG-UI SSE routes on a Starlette app instance."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.routing import Route

    async def ag_ui_run(request: Request) -> StreamingResponse:
        """Accept RunAgentInput, run agent, stream AG-UI events via SSE."""
        body = await request.body()
        try:
            data: dict = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})

        thread_id = data.get("threadId", str(uuid.uuid4())[:12])
        run_id = data.get("runId", thread_id)
        state = data.get("state", {})
        messages = data.get("messages", [])
        user_msg = _extract_user_message(messages)

        async def event_stream():
            ts = time.time()
            yield _sse({"type": "RUN_STARTED", "threadId": thread_id,
                         "runId": run_id, "timestamp": ts})
            if state:
                yield _sse({"type": "STATE_SNAPSHOT",
                             "snapshot": state, "timestamp": ts})

            tool_ctx = _build_tool_context(thread_id)
            try:
                agent_result = await _call_tool(
                    "agent_reason", {"task": user_msg, "context": tool_ctx},
                )
            except Exception as exc:
                logger.error("agent_reason failed: %s", exc)
                yield _sse({"type": "RUN_ERROR",
                             "message": f"Agent error: {exc}",
                             "timestamp": time.time()})
                return

            if isinstance(agent_result, dict):
                for tc_evt in await _execute_tool_calls(agent_result):
                    yield _sse(tc_evt)

            for evt in _extract_ag_ui_events(agent_result, thread_id):
                yield _sse(evt)

            yield _sse({"type": "RUN_FINISHED", "threadId": thread_id,
                         "runId": run_id, "timestamp": time.time()})

        return StreamingResponse(
            event_stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    app.routes.extend([
        Route("/ag-ui/run", ag_ui_run, methods=["POST"]),
    ])


def _extract_user_message(messages: list[dict]) -> str:
    """Extract the last user message from the messages array."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _extract_ag_ui_events(agent_result: Any, thread_id: str) -> list[dict]:
    """Map agent_reason result to AG-UI TEXT_MESSAGE events."""
    ts = time.time()
    msg_id = str(uuid.uuid4())[:8]
    text = ""
    if isinstance(agent_result, dict):
        text = agent_result.get("text", agent_result.get("output", ""))
        if not text:
            text = agent_result.get("result", str(agent_result))
    elif isinstance(agent_result, str):
        text = agent_result
    else:
        text = str(agent_result) if agent_result else ""
    if not text:
        return []
    return [
        {"type": "TEXT_MESSAGE_START", "messageId": msg_id,
         "role": "assistant", "timestamp": ts},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id,
         "delta": text, "timestamp": ts},
        {"type": "TEXT_MESSAGE_END", "messageId": msg_id, "timestamp": ts},
    ]


async def _execute_tool_calls(agent_result: dict) -> list[dict]:
    """Execute tool_calls from agent result, return AG-UI TOOL_CALL events."""
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
            result = await _call_tool(name, args if isinstance(args, dict) else {})
            payload = json.dumps(result) if result else "null"
        except Exception as exc:
            payload = json.dumps({"error": str(exc)})
        events.append({"type": "TOOL_CALL_END", "toolCallId": tc_id,
                        "result": payload, "timestamp": time.time()})
    return events


def _sse(event: dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(event)}\n\n"
