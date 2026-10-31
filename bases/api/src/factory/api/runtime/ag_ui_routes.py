"""AG-UI SSE endpoint — streams agent execution as AG-UI typed events.

Two paths share this route:

* ``CHAT_STREAMING=on`` drives the chat agent via
  ``factory.agent.interface.get_chat_agent_stream`` and the AG-UI
  mapper from the ui brick. Token streaming + inline tool-call cards.
* Legacy: ``agent_reason`` blocking call mapped at the end. Kept for
  callers that haven't migrated (dashboard ``agent_reason`` route).

This file is the thin transport shell — concrete path implementations
live in ``ag_ui_run_paths.py``.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

from .bridge import _call_tool, _extract_envelope, _get_aggregator

logger = logging.getLogger(__name__)
# CORS is applied globally via Starlette CORSMiddleware (see
# factory.mcp_utils.cors + the api/mcp_server composition roots).
# X-Accel-Buffering disables nginx output buffering; Content-Encoding
# identity defeats gzip middlewares — both keep deltas hot to the client.
_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Encoding": "identity",
}


def _streaming_enabled() -> bool:
    return os.environ.get("CHAT_STREAMING", "").lower() in (
        "1", "on", "true", "yes",
    )


def _build_tool_context(thread_id: str, run_id: str) -> dict[str, Any]:
    from .ag_ui_correlation import build_tool_context
    return build_tool_context(thread_id, run_id, _get_aggregator())


def _set_correlation_context(thread_id: str, run_id: str) -> Any:
    from .ag_ui_correlation import set_correlation_context
    return set_correlation_context(thread_id, run_id)


def _clear_correlation_context(scope: Any) -> None:
    from .ag_ui_correlation import clear_correlation_context
    clear_correlation_context(scope)


def register_ag_ui_routes(app) -> None:
    """Register AG-UI SSE routes on a FastAPI app instance."""
    from starlette.requests import Request
    from starlette.responses import StreamingResponse
    from starlette.routing import Route

    async def ag_ui_run(request: Request) -> StreamingResponse:
        body = await request.body()
        try:
            data: dict = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            return _error_response("Invalid JSON body")

        thread_id = data.get("threadId", str(uuid.uuid4())[:12])
        run_id = data.get("runId", thread_id)
        state = data.get("state", {})
        messages = data.get("messages", [])
        # bd-115z: FE-side tool registrations + canvas-context bullets.
        # Validate tools[] strictly — reject malformed runs with RUN_ERROR.
        # context[] is appended to the user message as a system prefix.
        fe_tools, fe_tools_error = _parse_fe_tools(data.get("tools", []))
        context_items = data.get("context", [])
        # bd:python-factory-d4roe.3: per-thread persona selector rides
        # forwardedProps.companion_x_agent_id. The base only parses +
        # forwards the opaque string (transport shell) — resolution,
        # validation, and the registry-miss → RUN_ERROR translation all
        # live in the chat adapter / stream path (verdict a19ef414 Q2).
        forwarded_props = data.get("forwardedProps", {})
        agent_id = _parse_agent_id(forwarded_props)
        model_id = _parse_model_id(forwarded_props)
        user_msg = _extract_user_message(messages)
        user_msg_with_ctx = _prefix_context(context_items, user_msg)
        identity = await _extract_envelope(request)
        from .ag_ui_steering import offer_busy_steer
        steer_event = await offer_busy_steer(
            thread_id, messages, user_msg, agent_id, identity,
        )

        async def event_stream():
            ts = time.time()
            reset_token = _set_correlation_context(thread_id, run_id)
            try:
                yield _sse({"type": "RUN_STARTED", "threadId": thread_id,
                             "runId": run_id, "timestamp": ts})
                if steer_event is not None:
                    yield _sse({**steer_event, "timestamp": time.time()})
                    yield _sse({"type": "RUN_FINISHED", "threadId": thread_id,
                                "runId": run_id, "timestamp": time.time()})
                    return
                if state:
                    yield _sse({"type": "STATE_SNAPSHOT",
                                 "snapshot": state, "timestamp": ts})
                if fe_tools_error is not None:
                    yield _sse({"type": "RUN_ERROR",
                                 "message": f"Invalid tools[]: {fe_tools_error}",
                                 "timestamp": time.time()})
                    return

                from .ag_ui_run_paths import (
                    RunPathOutcome, legacy_agent_reason, stream_chat,
                )
                outcome = RunPathOutcome()
                try:
                    if _streaming_enabled():
                        async for sse_evt in stream_chat(
                            thread_id, run_id, user_msg_with_ctx, _sse,
                            fe_tools=fe_tools, messages=messages,
                            agent_id=agent_id, model_id=model_id,
                            identity=identity, outcome=outcome,
                        ):
                            yield sse_evt
                    else:
                        async for sse_evt in legacy_agent_reason(
                            thread_id, run_id, user_msg_with_ctx,
                            _call_tool, _sse, _build_tool_context,
                            outcome=outcome,
                        ):
                            outcome.produced_output = True
                            yield sse_evt
                except Exception:  # noqa: BLE001 — HTTP 200 is already committed
                    logger.exception("AG-UI stream failed run_id=%s", run_id)
                    outcome.errored = True
                    yield _sse({"type": "RUN_ERROR",
                                "message": "Chat is temporarily unavailable. Please retry.",
                                "timestamp": time.time()})
                    return

                if outcome.errored:
                    return
                if not outcome.produced_output:
                    yield _sse({"type": "RUN_ERROR",
                                "message": "Chat completed without a response. Please retry.",
                                "timestamp": time.time()})
                    return
                yield _sse({"type": "RUN_FINISHED", "threadId": thread_id,
                             "runId": run_id, "timestamp": time.time()})
            finally:
                _clear_correlation_context(reset_token)

        return StreamingResponse(
            event_stream(), media_type="text/event-stream",
            headers=_STREAM_HEADERS,
        )

    app.routes.extend([
        Route("/ag-ui/run", ag_ui_run, methods=["POST"]),
    ])


def _extract_user_message(messages: list[dict]) -> str:
    from .ag_ui_helpers import extract_user_message
    return extract_user_message(messages)


def _parse_fe_tools(raw: Any) -> tuple[list[Any], str | None]:
    from .ag_ui_input import parse_fe_tools
    return parse_fe_tools(raw)


def _prefix_context(context_items: Any, user_msg: str) -> str:
    from .ag_ui_input import prefix_context
    return prefix_context(context_items, user_msg)


def _parse_agent_id(forwarded_props: Any) -> str | None:
    from .ag_ui_input import parse_agent_id
    return parse_agent_id(forwarded_props)


def _parse_model_id(forwarded_props: Any) -> str | None:
    from .ag_ui_input import parse_model_id
    return parse_model_id(forwarded_props)


def _sse(event: dict[str, Any]) -> str:
    from .ag_ui_helpers import sse
    return sse(event)


def _error_response(message: str):
    from .ag_ui_helpers import error_response
    return error_response(message)
