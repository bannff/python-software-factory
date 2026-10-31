"""Hypothesis property tests for AG-UI event mapper.

Properties verified:
1. map_event always returns a non-empty list for any dict input.
2. All output events have a valid AGUIEventType 'type' field.
3. All output events have a 'timestamp' field.
4. Text output events share the same messageId across the 3-event sequence.
5. Tool call events share the same toolCallId across the 3-event sequence.
6. make_state_snapshot always produces STATE_SNAPSHOT type.
7. make_state_delta always produces STATE_DELTA type.
"""

from hypothesis import given, settings, strategies as st

from factory.ui.runtime.ag_ui_mapper import (
    AGUIEventType,
    make_state_delta,
    make_state_snapshot,
    map_event,
)

_FAST = settings(max_examples=50)

_VALID_TYPES = frozenset({
    AGUIEventType.RUN_STARTED, AGUIEventType.RUN_FINISHED,
    AGUIEventType.RUN_ERROR, AGUIEventType.STEP_STARTED,
    AGUIEventType.STEP_FINISHED, AGUIEventType.TEXT_MESSAGE_START,
    AGUIEventType.TEXT_MESSAGE_CONTENT, AGUIEventType.TEXT_MESSAGE_END,
    AGUIEventType.TOOL_CALL_START, AGUIEventType.TOOL_CALL_ARGS,
    AGUIEventType.TOOL_CALL_END, AGUIEventType.STATE_SNAPSHOT,
    AGUIEventType.STATE_DELTA, AGUIEventType.MESSAGES_SNAPSHOT,
    AGUIEventType.CUSTOM,
})

_event_types = st.text(min_size=0, max_size=40)
_payloads = st.dictionaries(
    st.text(min_size=0, max_size=10),
    st.one_of(st.text(max_size=30), st.integers(), st.none(), st.booleans()),
    max_size=8,
)
_session_ids = st.text(
    min_size=0, max_size=12,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_state_dicts = st.dictionaries(
    st.text(min_size=1, max_size=10),
    st.one_of(st.text(max_size=20), st.integers(), st.floats(allow_nan=False),
              st.booleans(), st.none()),
    max_size=10,
)
_patch_ops = st.lists(
    st.fixed_dictionaries({
        "op": st.sampled_from(["add", "remove", "replace"]),
        "path": st.text(min_size=1, max_size=20),
        "value": st.one_of(st.text(max_size=10), st.integers(), st.none()),
    }),
    max_size=5,
)


class TestMapEventAlwaysReturns:
    """map_event never returns empty for any input dict."""

    @given(event_type=_event_types, payload=_payloads, sid=_session_ids)
    @_FAST
    def test_always_non_empty(self, event_type, payload, sid):
        result = map_event({"type": event_type, "payload": payload,
                            "session_id": sid})
        assert isinstance(result, list)
        assert len(result) >= 1


class TestAllEventsHaveValidType:
    """Every output event has a type in the AGUIEventType set."""

    @given(event_type=_event_types, payload=_payloads, sid=_session_ids)
    @_FAST
    def test_valid_type_field(self, event_type, payload, sid):
        result = map_event({"type": event_type, "payload": payload,
                            "session_id": sid})
        for evt in result:
            assert evt["type"] in _VALID_TYPES, f"Invalid type: {evt['type']}"


class TestAllEventsHaveTimestamp:
    """Every output event has a numeric timestamp."""

    @given(event_type=_event_types, payload=_payloads, sid=_session_ids)
    @_FAST
    def test_timestamp_present(self, event_type, payload, sid):
        result = map_event({"type": event_type, "payload": payload,
                            "session_id": sid})
        for evt in result:
            assert "timestamp" in evt
            assert isinstance(evt["timestamp"], float)


class TestTextSequenceSharedMessageId:
    """Text output 3-event sequences all share the same messageId."""

    @given(text=st.text(max_size=200), sid=_session_ids)
    @_FAST
    def test_shared_message_id(self, text, sid):
        result = map_event({"type": "agent.output.text",
                            "payload": {"text": text}, "session_id": sid})
        assert len(result) == 3
        mid = result[0]["messageId"]
        assert mid  # non-empty
        assert result[1]["messageId"] == mid
        assert result[2]["messageId"] == mid


class TestToolCallSequenceSharedId:
    """Tool call 3-event sequences all share the same toolCallId."""

    @given(name=st.text(min_size=1, max_size=30), sid=_session_ids)
    @_FAST
    def test_shared_tool_call_id(self, name, sid):
        result = map_event({"type": "agent.tool.call",
                            "payload": {"tool_name": name}, "session_id": sid})
        assert len(result) == 3
        tid = result[0]["toolCallId"]
        assert tid  # non-empty
        assert result[1]["toolCallId"] == tid
        assert result[2]["toolCallId"] == tid


class TestStateSnapshotProperty:
    """make_state_snapshot always produces STATE_SNAPSHOT with timestamp."""

    @given(state=_state_dicts)
    @_FAST
    def test_always_state_snapshot(self, state):
        snap = make_state_snapshot(state)
        assert snap["type"] == AGUIEventType.STATE_SNAPSHOT
        assert snap["snapshot"] == state
        assert isinstance(snap["timestamp"], float)


class TestStateDeltaProperty:
    """make_state_delta always produces STATE_DELTA with timestamp."""

    @given(patch=_patch_ops)
    @_FAST
    def test_always_state_delta(self, patch):
        delta = make_state_delta(patch)
        assert delta["type"] == AGUIEventType.STATE_DELTA
        assert delta["delta"] == patch
        assert isinstance(delta["timestamp"], float)
