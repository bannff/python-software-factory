from __future__ import annotations

from factory.agent.runtime.models import ToolCallDeltaEvent, ToolResultEvent
from factory.ui.runtime.ag_ui_activity_models import TerminalCommandActivity
from factory.ui.runtime.ag_ui_mapper_activity import AGUIActivityState, map_activity_event


def test_command_events_map_to_strict_terminal_activity() -> None:
    state = AGUIActivityState()
    opened = map_activity_event({
        "kind": "chat", "event": ToolCallDeltaEvent(
            tool_call_id="tool-1", tool_name="devtools_run_command",
        ),
    }, state)
    assert opened[0]["activityType"] == "terminal.command"
    assert opened[0]["replace"] is False

    started = map_activity_event({
        "kind": "workflow", "event": {
            "event_type": "devtools.command.started",
            "payload": {
                "run_id": "cmd_" + "a" * 32, "executable": "pytest",
                "cwd": "src", "sequence": 1,
            },
        },
    }, state)
    assert started[0]["type"] == "ACTIVITY_DELTA"
    assert started[0]["activityType"] == "terminal.command"

    output = map_activity_event({
        "kind": "workflow", "event": {
            "event_type": "devtools.command.output",
            "payload": {
                "run_id": "cmd_" + "a" * 32, "stream": "stdout",
                "text": "2 passed\n", "sequence": 2,
            },
        },
    }, state)
    assert output[0]["patch"][0] == {
        "op": "replace", "path": "/stdout", "value": "2 passed\n",
    }

    finished = map_activity_event({
        "kind": "workflow", "event": {
            "event_type": "devtools.command.finished",
            "payload": {
                "run_id": "cmd_" + "a" * 32, "exit_code": 0,
                "duration_ms": 25, "timed_out": False, "cancelled": False,
                "truncated": False, "success": True, "sequence": 3,
            },
        },
    }, state)
    assert any(item["value"] == "completed" for item in finished[0]["patch"])

    closed = map_activity_event({
        "kind": "chat", "event": ToolResultEvent(
            tool_call_id="tool-1", payload={
                "stdout": "2 passed\n", "stderr": "", "exit_code": 0,
                "duration_ms": 25, "timed_out": False,
                "cancelled": False, "truncated": False,
            },
        ),
    }, state)
    assert closed[0]["replace"] is True
    content = TerminalCommandActivity.model_validate(closed[0]["content"])
    assert content.status == "completed"
    assert content.command == "pytest" and content.stdout == "2 passed\n"
