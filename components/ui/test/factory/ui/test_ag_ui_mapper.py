"""Unit tests for AG-UI event mapper.

Tests each of the 7 internal event type mappings, 3-event sequences
for text/tool calls, unknown event fallback, and state helpers.
"""

import time

import pytest

from factory.ui.runtime.ag_ui_mapper import (
    AGUIEventType,
    make_state_delta,
    make_state_snapshot,
    map_event,
)


def _evt(event_type: str, payload: dict | None = None, sid: str = "s1") -> dict:
    return {"type": event_type, "payload": payload or {}, "session_id": sid}


class TestSessionStart:
    def test_produces_run_started(self):
        result = map_event(_evt("agent.session.start", {"run_id": "r1"}, "s1"))
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.RUN_STARTED
        assert result[0]["threadId"] == "s1"
        assert result[0]["runId"] == "r1"

    def test_run_id_defaults_to_session_id(self):
        result = map_event(_evt("agent.session.start", {}, "s2"))
        assert result[0]["runId"] == "s2"


class TestStepStart:
    def test_produces_step_started(self):
        result = map_event(_evt("agent.step.start", {"step_name": "plan"}))
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.STEP_STARTED
        assert result[0]["stepName"] == "plan"

    def test_falls_back_to_node_id(self):
        result = map_event(_evt("agent.step.start", {"node_id": "n1"}))
        assert result[0]["stepName"] == "n1"

    def test_empty_payload_gives_empty_step_name(self):
        result = map_event(_evt("agent.step.start"))
        assert result[0]["stepName"] == ""


class TestStepComplete:
    def test_produces_step_finished(self):
        result = map_event(_evt("agent.step.complete", {"step_name": "done"}))
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.STEP_FINISHED
        assert result[0]["stepName"] == "done"


class TestTextOutput:
    def test_produces_three_event_sequence(self):
        result = map_event(_evt("agent.output.text", {"text": "hello"}))
        assert len(result) == 3
        assert result[0]["type"] == AGUIEventType.TEXT_MESSAGE_START
        assert result[1]["type"] == AGUIEventType.TEXT_MESSAGE_CONTENT
        assert result[2]["type"] == AGUIEventType.TEXT_MESSAGE_END

    def test_all_share_same_message_id(self):
        result = map_event(_evt("agent.output.text", {"text": "hi"}))
        mid = result[0]["messageId"]
        assert mid and all(e["messageId"] == mid for e in result)

    def test_content_delta_matches_text(self):
        result = map_event(_evt("agent.output.text", {"text": "world"}))
        assert result[1]["delta"] == "world"

    def test_start_has_assistant_role(self):
        result = map_event(_evt("agent.output.text", {"text": "x"}))
        assert result[0]["role"] == "assistant"

    def test_empty_text(self):
        result = map_event(_evt("agent.output.text", {}))
        assert result[1]["delta"] == ""


class TestToolCall:
    def test_produces_three_event_sequence(self):
        result = map_event(_evt("agent.tool.call", {"tool_name": "search"}))
        assert len(result) == 3
        assert result[0]["type"] == AGUIEventType.TOOL_CALL_START
        assert result[1]["type"] == AGUIEventType.TOOL_CALL_ARGS
        assert result[2]["type"] == AGUIEventType.TOOL_CALL_END

    def test_all_share_same_tool_call_id(self):
        result = map_event(_evt("agent.tool.call", {"tool_name": "t"}))
        tid = result[0]["toolCallId"]
        assert tid and all(e["toolCallId"] == tid for e in result)

    def test_tool_name_in_start(self):
        result = map_event(_evt("agent.tool.call", {"tool_name": "fetch"}))
        assert result[0]["toolCallName"] == "fetch"

    def test_missing_tool_name_defaults_to_unknown(self):
        result = map_event(_evt("agent.tool.call", {}))
        assert result[0]["toolCallName"] == "unknown"

    def test_args_and_result(self):
        payload = {"tool_name": "t", "arguments_summary": '{"q":"x"}',
                    "result_summary": "ok"}
        result = map_event(_evt("agent.tool.call", payload))
        assert result[1]["delta"] == '{"q":"x"}'
        assert result[2]["result"] == "ok"


class TestWorkflowComplete:
    def test_success_produces_run_finished(self):
        result = map_event(_evt("agent.workflow.complete", {"status": "completed"}))
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.RUN_FINISHED

    def test_failed_produces_run_error(self):
        result = map_event(_evt("agent.workflow.complete",
                                {"status": "failed", "summary": "boom"}))
        assert result[0]["type"] == AGUIEventType.RUN_ERROR
        assert result[0]["message"] == "boom"

    def test_error_status_also_produces_run_error(self):
        result = map_event(_evt("agent.workflow.complete", {"status": "error"}))
        assert result[0]["type"] == AGUIEventType.RUN_ERROR

    def test_default_status_is_completed(self):
        result = map_event(_evt("agent.workflow.complete", {}))
        assert result[0]["type"] == AGUIEventType.RUN_FINISHED


class TestUnknownEvent:
    def test_unknown_type_maps_to_custom(self):
        result = map_event(_evt("some.random.event", {"data": 42}))
        assert len(result) == 1
        assert result[0]["type"] == AGUIEventType.CUSTOM
        assert result[0]["name"] == "some.random.event"
        assert result[0]["value"] == {"data": 42}

    def test_empty_type_maps_to_custom(self):
        result = map_event({"payload": {}})
        assert result[0]["type"] == AGUIEventType.CUSTOM


class TestTimestamps:
    def test_all_events_have_timestamp(self):
        before = time.time()
        result = map_event(_evt("agent.output.text", {"text": "t"}))
        after = time.time()
        for e in result:
            assert before <= e["timestamp"] <= after


class TestStateHelpers:
    def test_make_state_snapshot(self):
        snap = make_state_snapshot({"count": 5})
        assert snap["type"] == AGUIEventType.STATE_SNAPSHOT
        assert snap["snapshot"] == {"count": 5}
        assert "timestamp" in snap

    def test_make_state_delta(self):
        patch = [{"op": "replace", "path": "/count", "value": 6}]
        delta = make_state_delta(patch)
        assert delta["type"] == AGUIEventType.STATE_DELTA
        assert delta["delta"] == patch
        assert "timestamp" in delta

    def test_empty_state_snapshot(self):
        snap = make_state_snapshot({})
        assert snap["snapshot"] == {}

    def test_empty_delta(self):
        delta = make_state_delta([])
        assert delta["delta"] == []
