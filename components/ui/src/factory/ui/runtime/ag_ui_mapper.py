"""AG-UI event mapper — translates internal events to AG-UI protocol events.

Pure functions, no side effects. Input: internal event dict.
Output: list of AG-UI event dicts (one internal event may produce
multiple AG-UI events, e.g., text → START + CONTENT + END).
"""

from __future__ import annotations

import time
import uuid
from typing import Any


class AGUIEventType:
    """AG-UI protocol event types."""

    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    REASONING_MESSAGE_START = "REASONING_MESSAGE_START"
    REASONING_MESSAGE_CONTENT = "REASONING_MESSAGE_CONTENT"
    REASONING_MESSAGE_END = "REASONING_MESSAGE_END"
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    MESSAGES_SNAPSHOT = "MESSAGES_SNAPSHOT"
    ACTIVITY_SNAPSHOT = "ACTIVITY_SNAPSHOT"
    ACTIVITY_DELTA = "ACTIVITY_DELTA"
    CUSTOM = "CUSTOM"


def map_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Map an internal agent event to AG-UI event(s).

    Args:
        event: Internal event dict with 'type' and 'payload' keys.

    Returns:
        List of AG-UI event dicts. May be 1:1 or 1:N mapping.
    """
    event_type = event.get("type", "")
    payload = event.get("payload", {})
    session_id = event.get("session_id", "")
    ts = _timestamp()
    mapper = _MAPPERS.get(event_type, _map_unknown)
    return mapper(event_type, payload, session_id, ts)


def make_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Create a STATE_SNAPSHOT AG-UI event."""
    return {"type": AGUIEventType.STATE_SNAPSHOT,
            "snapshot": state, "timestamp": _timestamp()}


def make_state_delta(patch: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a STATE_DELTA AG-UI event (JSON Patch RFC 6902)."""
    return {"type": AGUIEventType.STATE_DELTA,
            "delta": patch, "timestamp": _timestamp()}


def _map_session_start(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    return [{"type": AGUIEventType.RUN_STARTED,
             "threadId": session_id,
             "runId": payload.get("run_id", session_id),
             "timestamp": ts}]


def _map_step_start(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    return [{"type": AGUIEventType.STEP_STARTED,
             "stepName": payload.get("step_name", payload.get("node_id", "")),
             "timestamp": ts}]


def _map_step_complete(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    return [{"type": AGUIEventType.STEP_FINISHED,
             "stepName": payload.get("step_name", payload.get("node_id", "")),
             "timestamp": ts}]


def _map_text_output(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    msg_id = str(uuid.uuid4())[:8]
    text = payload.get("text", "")
    return [
        {"type": AGUIEventType.TEXT_MESSAGE_START,
         "messageId": msg_id, "role": "assistant", "timestamp": ts},
        {"type": AGUIEventType.TEXT_MESSAGE_CONTENT,
         "messageId": msg_id, "delta": text, "timestamp": ts},
        {"type": AGUIEventType.TEXT_MESSAGE_END,
         "messageId": msg_id, "timestamp": ts},
    ]


def _map_tool_call(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    tool_id = str(uuid.uuid4())[:8]
    return [
        {"type": AGUIEventType.TOOL_CALL_START, "toolCallId": tool_id,
         "toolCallName": payload.get("tool_name", "unknown"), "timestamp": ts},
        {"type": AGUIEventType.TOOL_CALL_ARGS, "toolCallId": tool_id,
         "delta": str(payload.get("arguments_summary", "{}")), "timestamp": ts},
        {"type": AGUIEventType.TOOL_CALL_END, "toolCallId": tool_id,
         "result": str(payload.get("result_summary", "")), "timestamp": ts},
    ]


def _map_workflow_complete(
    _type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    status = payload.get("status", "completed")
    if status in ("failed", "error"):
        return [{"type": AGUIEventType.RUN_ERROR,
                 "message": payload.get("summary", "Workflow failed"),
                 "timestamp": ts}]
    return [{"type": AGUIEventType.RUN_FINISHED,
             "threadId": session_id, "timestamp": ts}]


def _map_unknown(
    event_type: str, payload: dict, session_id: str, ts: float,
) -> list[dict]:
    return [{"type": AGUIEventType.CUSTOM, "name": event_type,
             "value": payload, "timestamp": ts}]


def _timestamp() -> float:
    """Current time as Unix timestamp."""
    return time.time()


_MAPPERS = {
    "agent.session.start": _map_session_start,
    "agent.step.start": _map_step_start,
    "agent.step.complete": _map_step_complete,
    "agent.output.text": _map_text_output,
    "agent.tool.call": _map_tool_call,
    "agent.workflow.complete": _map_workflow_complete,
}
