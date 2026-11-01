"""A successful ui_paint_canvas result must reach the AG-UI mapper as a state_delta (#56)."""
from __future__ import annotations

import json

from factory.agent.runtime.adapters.strands_stream import strands_event_tuples

PAINT = {
    "schema_version": "v1", "ok": True, "error": None,
    "data": {"_a2ui_canvas": {
        "target": "live", "mode": "snapshot",
        "payload": {"components": [{"type": "heading", "text": "Live Probe"}]},
    }},
}


def _tool_result_message(payload: dict) -> dict:
    block = {"toolResult": {
        "toolUseId": "call-1", "status": "success",
        "content": [{"text": json.dumps(payload)}],
    }}
    return {"message": {"role": "user", "content": [block]}}


def test_paint_result_emits_state_delta_after_the_tool_result() -> None:
    events = strands_event_tuples(_tool_result_message(PAINT))
    assert [kind for kind, _ in events] == ["tool_result", "state_delta"]
    assert events[1][1] == {
        "target": "live", "mode": "snapshot", "payload": PAINT["data"]["_a2ui_canvas"]["payload"],
    }


def test_failed_or_malformed_paint_emits_no_state_delta() -> None:
    failed = {**PAINT, "ok": False, "error": "boom"}
    wrong_slot = {**PAINT, "data": {"_a2ui_canvas": {**PAINT["data"]["_a2ui_canvas"], "target": "nowhere"}}}
    for payload in (failed, wrong_slot, {"schema_version": "v1", "ok": True, "error": None, "data": {}}):
        assert [k for k, _ in strands_event_tuples(_tool_result_message(payload))] == ["tool_result"]
