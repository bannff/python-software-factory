"""Property tests for ``map_chat_stream_event``.

Single-invocation invariants checked here. The stateful state-machine
test for arbitrary event sequences lives in
``test_ag_ui_mapper_chat_stream_machine.py`` so each file stays under
the 200 LOC cap.
"""
from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, given, settings, strategies as st

from factory.agent.runtime.models import (
    DoneEvent, ErrorEvent, ReasoningTextEvent, StepFinishEvent,
    StepStartEvent, TextDeltaEvent, ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)

from ._ag_ui_mapper_invariants import check_invariants


# --- @given sanity check ----------------------------------------------------


@st.composite
def _safe_event(draw: st.DrawFn) -> Any:
    short = st.text(min_size=1, max_size=8)
    kind = draw(st.sampled_from([
        "text", "tool_start", "tool_args", "tool_result",
        "step_start", "step_finish", "reasoning",
    ]))
    if kind == "text":
        return TextDeltaEvent(content=draw(short),
                               message_id=draw(short))
    if kind == "tool_start":
        return ToolCallDeltaEvent(
            tool_call_id=draw(short),
            tool_name=draw(short), args_delta="",
        )
    if kind == "tool_args":
        return ToolCallDeltaEvent(
            tool_call_id=draw(short),
            tool_name=None, args_delta=draw(short),
        )
    if kind == "tool_result":
        return ToolResultEvent(
            tool_call_id=draw(short),
            payload=draw(st.text(max_size=20)),
            is_error=draw(st.booleans()),
        )
    if kind == "step_start":
        return StepStartEvent(step_name=draw(short))
    if kind == "step_finish":
        return StepFinishEvent(step_name=draw(short))
    return ReasoningTextEvent(content=draw(short))


@given(st.lists(_safe_event(), min_size=0, max_size=20))
@settings(max_examples=80, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_arbitrary_sequence_holds_invariants(events: list[Any]) -> None:
    """Any sequence followed by ``done`` keeps the AG-UI invariants."""
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    for e in events:
        out.extend(map_chat_stream_event(e, state))
    out.extend(map_chat_stream_event(DoneEvent(reason="stop"), state))
    check_invariants(out)
    assert state.terminated is True


def test_done_closes_open_message() -> None:
    state = AGUIStreamState()
    out = map_chat_stream_event(
        TextDeltaEvent(content="hi", message_id="m1"), state,
    )
    assert any(e["type"] == "TEXT_MESSAGE_START" for e in out)
    out2 = map_chat_stream_event(DoneEvent(reason="stop"), state)
    assert any(e["type"] == "TEXT_MESSAGE_END" for e in out2)
    assert state.terminated is True


def test_error_closes_open_message_and_emits_run_error() -> None:
    state = AGUIStreamState()
    map_chat_stream_event(
        TextDeltaEvent(content="hi", message_id="m1"), state,
    )
    out = map_chat_stream_event(ErrorEvent(message="boom"), state)
    types = [e["type"] for e in out]
    assert "TEXT_MESSAGE_END" in types
    assert "RUN_ERROR" in types
    assert state.terminated is True


def test_no_events_after_terminal() -> None:
    state = AGUIStreamState()
    map_chat_stream_event(DoneEvent(reason="stop"), state)
    assert map_chat_stream_event(
        TextDeltaEvent(content="late", message_id="m"), state,
    ) == []


def test_tool_call_lifecycle() -> None:
    state = AGUIStreamState()
    a = map_chat_stream_event(ToolCallDeltaEvent(
        tool_call_id="tc1", tool_name="kb_search"), state)
    b = map_chat_stream_event(ToolCallDeltaEvent(
        tool_call_id="tc1", tool_name=None, args_delta='{"q":"x"}'), state)
    c = map_chat_stream_event(ToolResultEvent(
        tool_call_id="tc1", payload={"hits": 3}), state)
    types = [e["type"] for e in a + b + c]
    assert types == [
        "TOOL_CALL_START", "TOOL_CALL_ARGS",
        "TOOL_CALL_END", "TOOL_CALL_RESULT",
    ]
    result_evt = c[-1]
    assert result_evt["toolCallId"] == "tc1"
    assert result_evt["role"] == "tool"
    import json as _j
    assert _j.loads(result_evt["content"]) == {"hits": 3}


def test_reasoning_emits_canonical_message_trio() -> None:
    state = AGUIStreamState()
    out = map_chat_stream_event(ReasoningTextEvent(content="think"), state)
    types = [e["type"] for e in out]
    assert types == ["REASONING_MESSAGE_START", "REASONING_MESSAGE_CONTENT"]
    msg_id = out[0]["messageId"]
    assert out[0]["role"] == "reasoning"
    assert out[1]["messageId"] == msg_id
    assert out[1]["delta"] == "think"
    out2 = map_chat_stream_event(DoneEvent(reason="stop"), state)
    types2 = [e["type"] for e in out2]
    assert "REASONING_MESSAGE_END" in types2
    end = next(e for e in out2 if e["type"] == "REASONING_MESSAGE_END")
    assert end["messageId"] == msg_id


def test_reasoning_close_on_done() -> None:
    """Two reasoning chunks then done → 1 START, 2 CONTENT, 1 END."""
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    out.extend(map_chat_stream_event(ReasoningTextEvent(content="a"), state))
    out.extend(map_chat_stream_event(ReasoningTextEvent(content="b"), state))
    out.extend(map_chat_stream_event(DoneEvent(reason="stop"), state))
    starts = [e for e in out if e["type"] == "REASONING_MESSAGE_START"]
    contents = [e for e in out if e["type"] == "REASONING_MESSAGE_CONTENT"]
    ends = [e for e in out if e["type"] == "REASONING_MESSAGE_END"]
    assert len(starts) == 1
    assert len(contents) == 2
    assert len(ends) == 1
    msg_id = starts[0]["messageId"]
    assert all(c["messageId"] == msg_id for c in contents)
    assert ends[0]["messageId"] == msg_id
    assert [c["delta"] for c in contents] == ["a", "b"]


def test_interleaved_thinking_brackets_correctly() -> None:
    """Claude 4 interleaved thinking → 3 distinct REASONING_MESSAGE pairs."""
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    out.extend(map_chat_stream_event(ReasoningTextEvent(content="a"), state))
    out.extend(map_chat_stream_event(
        TextDeltaEvent(content="hi", message_id="m1"), state))
    out.extend(map_chat_stream_event(ReasoningTextEvent(content="b"), state))
    out.extend(map_chat_stream_event(
        ToolCallDeltaEvent(tool_call_id="t1", tool_name="kb"), state))
    out.extend(map_chat_stream_event(
        ToolResultEvent(tool_call_id="t1", payload="ok"), state))
    out.extend(map_chat_stream_event(ReasoningTextEvent(content="c"), state))
    out.extend(map_chat_stream_event(DoneEvent(reason="stop"), state))
    starts = [e for e in out if e["type"] == "REASONING_MESSAGE_START"]
    ends = [e for e in out if e["type"] == "REASONING_MESSAGE_END"]
    assert len(starts) == 3
    assert len(ends) == 3
    # Distinct messageIds per pair.
    ids = [s["messageId"] for s in starts]
    assert len(set(ids)) == 3
    # Each START precedes its matching END in stream order.
    for s in starts:
        mid = s["messageId"]
        end = next(e for e in ends if e["messageId"] == mid)
        assert out.index(s) < out.index(end)
    check_invariants(out)


# --- bd:python-factory-lmne / bd:python-factory-3uhr ---
# Synth END+RESULT pair tests live in
# ``test_ag_ui_mapper_chat_stream_synth.py`` so each file stays under
# the 200 LOC cap.

