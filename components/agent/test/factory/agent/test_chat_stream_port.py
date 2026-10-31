"""Unit + property tests for ``ChatAgentPort.stream`` (memory adapter).

The Strands MCP adapter has its own dedicated test module
(``test_strands_mcp_chat_stream.py``). This file focuses on the port
contract via the in-memory mock — it must produce a deterministic event
sequence that satisfies the same invariants as the production adapter.

Run:
    uv run pytest components/agent/test/factory/agent/test_chat_stream_port.py -v
"""
from __future__ import annotations

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from factory.agent.runtime.adapters.memory import MemoryChatAgent
from factory.agent.runtime.models import (
    ChatStreamEvent,
    DoneEvent,
    ErrorEvent,
    ReasoningTextEvent,
    StepFinishEvent,
    StepStartEvent,
    TextDeltaEvent,
    ToolCallDeltaEvent,
    ToolResultEvent,
)
from pydantic import TypeAdapter, ValidationError


_ADAPTER: TypeAdapter[ChatStreamEvent] = TypeAdapter(ChatStreamEvent)


@pytest.mark.asyncio
async def test_memory_stream_emits_three_events_in_order() -> None:
    agent = MemoryChatAgent()
    events = [evt async for evt in agent.stream("t1", "hello")]
    assert len(events) == 3
    assert isinstance(events[0], TextDeltaEvent)
    assert isinstance(events[1], TextDeltaEvent)
    assert isinstance(events[2], DoneEvent)
    assert events[0].message_id == events[1].message_id
    # The two deltas concatenate to the canned mock text.
    assert events[0].content + events[1].content == "Hello world"
    assert events[2].reason == "stop"


@pytest.mark.asyncio
async def test_memory_stream_unique_message_id_per_turn() -> None:
    agent = MemoryChatAgent()
    first = [e async for e in agent.stream("thread-a", "hi")]
    second = [e async for e in agent.stream("thread-a", "hi again")]
    msg_ids_first = {e.message_id for e in first if isinstance(e, TextDeltaEvent)}
    msg_ids_second = {e.message_id for e in second if isinstance(e, TextDeltaEvent)}
    assert msg_ids_first.isdisjoint(msg_ids_second)


@pytest.mark.asyncio
async def test_memory_stream_isolates_threads() -> None:
    agent = MemoryChatAgent()
    a = [e async for e in agent.stream("thread-a", "msg")]
    b = [e async for e in agent.stream("thread-b", "msg")]
    a_ids = {e.message_id for e in a if isinstance(e, TextDeltaEvent)}
    b_ids = {e.message_id for e in b if isinstance(e, TextDeltaEvent)}
    assert a_ids.isdisjoint(b_ids)


@pytest.mark.asyncio
async def test_memory_close_clears_history() -> None:
    agent = MemoryChatAgent()
    _ = [e async for e in agent.stream("t", "hi")]
    agent.close("t")
    second = [e async for e in agent.stream("t", "hi")]
    # After close, the turn counter resets — message_id starts at 1 again.
    text = next(e for e in second if isinstance(e, TextDeltaEvent))
    assert text.message_id.endswith("-1")


# --- discriminated union round-trip property test ---------------------------


@st.composite
def _arbitrary_event(draw: st.DrawFn) -> ChatStreamEvent:
    """Strategy generating any ChatStreamEvent variant with safe payloads."""
    kind = draw(st.sampled_from([
        "text_delta", "tool_call_delta", "tool_result",
        "reasoning_text", "step_start", "step_finish", "done", "error",
    ]))
    short = st.text(min_size=0, max_size=20)
    if kind == "text_delta":
        return TextDeltaEvent(content=draw(short), message_id=draw(short.filter(bool) | st.just("m")))
    if kind == "tool_call_delta":
        return ToolCallDeltaEvent(
            tool_call_id=draw(short.filter(bool) | st.just("tc")),
            tool_name=draw(st.one_of(st.none(), short)),
            args_delta=draw(short),
        )
    if kind == "tool_result":
        return ToolResultEvent(
            tool_call_id=draw(short.filter(bool) | st.just("tc")),
            payload=draw(st.one_of(
                st.none(), st.integers(), st.text(max_size=30),
                st.dictionaries(short, st.integers(), max_size=3),
            )),
            is_error=draw(st.booleans()),
        )
    if kind == "reasoning_text":
        return ReasoningTextEvent(content=draw(short))
    if kind == "step_start":
        return StepStartEvent(step_name=draw(short.filter(bool) | st.just("s")))
    if kind == "step_finish":
        return StepFinishEvent(step_name=draw(short.filter(bool) | st.just("s")))
    if kind == "done":
        return DoneEvent(reason=draw(st.sampled_from(
            ["stop", "tool_use", "max_tokens", "error"],
        )))
    return ErrorEvent(message=draw(short))


@given(_arbitrary_event())
@settings(max_examples=80, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_chat_stream_event_round_trip(event: ChatStreamEvent) -> None:
    """``model_dump_json`` → ``model_validate_json`` is identity."""
    raw = event.model_dump_json()
    rebuilt = _ADAPTER.validate_json(raw)
    assert rebuilt == event


def test_chat_stream_event_extra_fields_forbidden() -> None:
    """``ConfigDict(extra="forbid")`` rejects rogue keys — leaks would fail."""
    with pytest.raises(ValidationError):
        TextDeltaEvent.model_validate(
            {"type": "text_delta", "content": "x",
             "message_id": "m", "rogue": "leak"},
        )


@pytest.mark.asyncio
async def test_memory_stream_terminates_with_done() -> None:
    """Last event of every clean stream is a DoneEvent."""
    agent = MemoryChatAgent()
    last: ChatStreamEvent | None = None
    async for evt in agent.stream("t", "hi"):
        last = evt
    assert isinstance(last, DoneEvent)
    # asyncio sanity — ensure the iterator doesn't leave dangling tasks.
    await asyncio.sleep(0)
