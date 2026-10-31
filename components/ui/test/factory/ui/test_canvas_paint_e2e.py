"""Compatibility checks for the surviving canvas carrier contracts.

The former Strands hook/plugin bridge no longer exists. These tests deliberately
cover only current public boundaries: paint output, tool-result mapping, and
state-event mapping. They do not synthesize or claim a production bridge.
"""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.models import (
    StateDeltaEvent, ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.mcp.paint_canvas import register as register_paint
from factory.ui.runtime.ag_ui_mapper import AGUIEventType
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)

_PAYLOAD = {
    "components": [{"id": "u1", "type": "card", "props": {"title": "kiro-agent"}}],
    "name": "graph",
}
_TCID = "tc-paint-1"


def _make_paint_tool():
    class _Harness:
        tools: dict[str, Any] = {}

        def tool(self):
            def decorate(function):
                self.tools[function.__name__] = function
                return function
            return decorate

    harness = _Harness()
    register_paint(harness, get_runtime=lambda: None)
    tool = harness.tools["ui_paint_canvas"]

    def invoke(**kwargs: Any) -> dict[str, Any]:
        result = tool(**kwargs)
        return {"error": result.error} if not result.ok else result.data.model_dump(by_alias=True)

    return invoke


def test_paint_canvas_emits_exact_typed_sentinel() -> None:
    result = _make_paint_tool()(target="graph", payload=_PAYLOAD, mode="snapshot")
    assert result["_a2ui_canvas"] == {
        "target": "graph", "mode": "snapshot", "payload": _PAYLOAD,
    }


def test_tool_result_mapper_emits_result_after_seen_call() -> None:
    state = AGUIStreamState()
    map_chat_stream_event(
        ToolCallDeltaEvent(tool_call_id=_TCID, tool_name="ui_paint_canvas"), state,
    )
    wire = map_chat_stream_event(
        ToolResultEvent(tool_call_id=_TCID, payload={"rendered": True}), state,
    )
    assert [item["type"] for item in wire][-1] == AGUIEventType.TOOL_CALL_RESULT


def test_state_event_mapper_emits_canvas_snapshot() -> None:
    wire = map_chat_stream_event(
        StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD),
        AGUIStreamState(),
    )
    assert wire[0]["type"] == AGUIEventType.STATE_SNAPSHOT
    assert wire[0]["snapshot"] == {"canvas": {"graph": _PAYLOAD}}
