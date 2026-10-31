"""Streaming + legacy run paths for the AG-UI SSE endpoint.

Extracted from ``ag_ui_routes.py`` to keep that file <200 LOC. Each
function is an async generator that yields SSE-formatted strings; the
route stitches RUN_STARTED/STATE_SNAPSHOT/RUN_FINISHED around them.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RunPathOutcome:
    """Mutable error status shared with the enclosing SSE route."""

    errored: bool = False
    produced_output: bool = False


def open_chat_span(
    thread_id: str, run_id: str,
    *, model_id: str | None = None,
    thinking_budget: int | None = None,
    fe_tools_count: int | None = None,
    messages_count: int | None = None,
):
    """Open an OTel span for the chat-streaming run.

    Returns the entered context manager (or None when OTel isn't
    installed). The caller hands the value back to ``close_span``.

    bd-tq76: optional kwargs surface useful debugging context. The
    Strands SDK auto-emits child spans (invoke_agent / chat /
    execute_tool) under this span via ``StrandsTelemetry``; no plugin
    needed (verdicts: meta-architect 4d64e1e5, strands-expert
    a98a89b4 — both REJECT a TracingPlugin shim).
    """
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("factory.api.ag_ui")
        attrs: dict[str, Any] = {
            "brick.name": "agent", "tool.name": "chat_stream",
            "thread_id": thread_id, "run_id": run_id,
        }
        if model_id is not None:
            attrs["model_id"] = model_id
        if thinking_budget is not None:
            attrs["thinking_budget"] = thinking_budget
        if fe_tools_count is not None:
            attrs["fe_tools_count"] = fe_tools_count
        if messages_count is not None:
            attrs["messages_count"] = messages_count
        cm = tracer.start_as_current_span(
            "brick.tool.agent.chat_stream", attributes=attrs,
        )
        cm.__enter__()
        return cm
    except Exception:  # noqa: BLE001 — OTel optional
        return None


def close_span(cm: Any) -> None:
    if cm is None:
        return
    try:
        cm.__exit__(None, None, None)
    except Exception:  # noqa: BLE001
        pass


async def stream_chat(
    thread_id: str, run_id: str, user_msg: str, sse,
    fe_tools: list[Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    identity: dict[str, str] | None = None,
    outcome: RunPathOutcome | None = None,
):
    """Chat-streaming path.

    Wraps the merged chat-agent + event_bus stream in an OTel span and
    runs each item through three pure-fn mappers (chat / workflow /
    activity). Yields SSE strings.

    ``fe_tools`` (bd-115z) is forwarded to the chat adapter via
    ``merged_chat_stream`` → ``get_chat_agent_stream``. ``messages``
    (bd-n368) lets the chat adapter sync FE-handler replies on resume
    turns. ``agent_id`` (bd-d4roe.3) is the per-thread persona selector
    from ``forwardedProps.companion_x_agent_id`` — threaded opaquely to
    the adapter, which resolves it (or LOUD-FAILs → ErrorEvent →
    RUN_ERROR). ``map_activity_event`` (bd-6zyg) consumes the merged
    stream alongside the existing chat + workflow mappers and emits
    ``ACTIVITY_SNAPSHOT`` / ``ACTIVITY_DELTA`` for sub-agent runs.
    """
    from .ag_ui_chat_stream import merged_chat_stream
    from factory.ui.interface import (
        AGUIActivityState, AGUIStreamState,
        map_activity_event, map_chat_stream_event,
    )
    from .ag_ui_mapper_workflow import map_workflow_event

    state = AGUIStreamState()
    activity_state = AGUIActivityState()
    span_cm = open_chat_span(
        thread_id, run_id, model_id=model_id,
        fe_tools_count=len(fe_tools or []),
        messages_count=len(messages or []),
    )
    try:
        async for item in merged_chat_stream(
            thread_id, user_msg, run_id,
            fe_tools=fe_tools, messages=messages,
            agent_id=agent_id, model_id=model_id, identity=identity,
        ):
            kind = item["kind"]
            if kind == "chat":
                ag_ui_events = map_chat_stream_event(item["event"], state)
            elif kind == "workflow":
                ag_ui_events = map_workflow_event(item["event"])
            else:
                ag_ui_events = []
            for evt in map_activity_event(item, activity_state):
                yield sse(evt)
            for evt in ag_ui_events:
                event_type = evt.get("type")
                if outcome is not None:
                    if event_type == "RUN_ERROR":
                        outcome.errored = True
                    elif event_type == "TOOL_CALL_START":
                        # A tool call was actually attempted — legitimate
                        # output even when it hands off to the frontend
                        # with END-only (no RESULT), e.g. the
                        # ``_frontend_pending`` sentinel path and the
                        # ``fe_approve_shell`` HITL synth.
                        outcome.produced_output = True
                    elif event_type == "TEXT_MESSAGE_CONTENT" and str(
                        evt.get("delta", "")
                    ).strip():
                        outcome.produced_output = True
                    elif event_type == "TOOL_CALL_RESULT":
                        outcome.produced_output = True
                yield sse(evt)
            if state.terminated:
                break
    finally:
        close_span(span_cm)


async def legacy_agent_reason(
    thread_id: str, run_id: str, user_msg: str,
    call_tool, sse, build_tool_context,
    outcome: RunPathOutcome | None = None,
):
    """Legacy non-streaming path: ``agent_reason`` → AG-UI events.

    Kept for callers that haven't migrated to chat streaming (dashboard
    chat routes, headless evals, anything that targets ``/ag-ui/run``
    with ``CHAT_STREAMING`` off).
    """
    from .ag_ui_helpers import (
        execute_tool_calls, extract_ag_ui_events,
    )

    tool_ctx = build_tool_context(thread_id, run_id)
    try:
        agent_result = await call_tool(
            "agent_reason", {"task": user_msg, "context": tool_ctx},
        )
    except Exception:  # noqa: BLE001 — expose only a stable safe error
        logger.exception("agent_reason failed run_id=%s", run_id)
        if outcome is not None:
            outcome.errored = True
        yield sse({"type": "RUN_ERROR",
                    "message": "Chat is temporarily unavailable. Please retry.",
                    "timestamp": time.time()})
        return

    if isinstance(agent_result, dict):
        for tc_evt in await execute_tool_calls(agent_result, call_tool):
            yield sse(tc_evt)
    for evt in extract_ag_ui_events(agent_result, thread_id):
        yield sse(evt)


__all__ = ["stream_chat", "legacy_agent_reason",
           "open_chat_span", "close_span"]
