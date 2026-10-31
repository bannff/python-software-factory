from __future__ import annotations

from factory.agent.runtime.models import ToolCallDeltaEvent, ToolResultEvent
from factory.ui.runtime.ag_ui_mapper_activity import AGUIActivityState, map_activity_event


def _chat(event):
    return {"kind": "chat", "event": event}


def _workflow(event_type: str, run_id: str, **payload):
    return {"kind": "workflow", "event": {
        "event_type": event_type,
        "payload": {"run_id": run_id, **payload},
    }}


def test_background_activity_tracks_durable_workflow_run() -> None:
    state = AGUIActivityState()
    opened = map_activity_event(_chat(ToolCallDeltaEvent(
        tool_call_id="tool-1", tool_name="agent_spawn_background",
    )), state)
    assert opened[0]["messageId"] == "subagent:tool-1"
    assert opened[0]["content"]["status"] == "running"

    bound = map_activity_event(_chat(ToolResultEvent(
        tool_call_id="tool-1",
        payload={"run_id": "workflow-1", "agent_id": "reviewer"},
    )), state)
    assert bound[0]["messageId"] == "subagent:tool-1"
    assert bound[0]["content"]["run_id"] == "workflow-1"
    assert "workflow-1" in state.runs_by_run_id

    started = map_activity_event(_workflow(
        "workflow.attempt_started", "workflow-1",
        step_id="execute", agent_id="reviewer",
    ), state)
    assert started[0]["type"] == "ACTIVITY_DELTA"
    assert started[0]["messageId"] == "subagent:tool-1"
    assert started[0]["patch"][0]["value"]["node_id"] == "reviewer"

    stopped = map_activity_event(_workflow(
        "workflow.attempt_completed", "workflow-1",
        step_id="execute", agent_id="reviewer", status="succeeded",
    ), state)
    assert any(op["value"] == "completed" for op in stopped[0]["patch"])

    terminal = map_activity_event(_workflow(
        "workflow.run_succeeded", "workflow-1", status="succeeded",
    ), state)
    assert terminal[0]["type"] == "ACTIVITY_SNAPSHOT"
    assert terminal[0]["messageId"] == "subagent:tool-1"
    assert terminal[0]["content"]["status"] == "completed"
    assert state.runs_by_run_id == {}
