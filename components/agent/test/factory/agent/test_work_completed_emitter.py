"""WorkCompletedEmitterPlugin — fired on a REAL strands chat turn, and
replay-safe (epic #124 S4a). Fakes shared: ``_work_completed_fakes``."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("strands")

from strands.hooks import AfterInvocationEvent

from factory.agent.runtime.adapters.strands_agent_factory import _CURRENT_INVOCATION
from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent
from factory.agent.runtime.personas import DEFAULT_AGENT_ID

from ._strands_contract_fakes import NullClient, RepliedModel, _chat
from ._work_completed_fakes import EventsToolFake

_PAYLOAD_KEYS = {"run_id", "agent_id", "input_summary", "output_summary",
                 "idempotency_key"}


def _hook(chat: StrandsChatAgent, events: EventsToolFake) -> Any:
    chat._work._invoker = events
    return chat._work


async def test_stream_turn_emits_chat_turn_completed() -> None:
    """First check: one live streamed chat turn publishes chat.turn.completed
    with exactly the handler-consumed payload keys (+ its dedupe key);
    tenant/principal ride the envelope, never the payload."""
    chat = _chat(RepliedModel())
    events = EventsToolFake()
    hook = _hook(chat, events)

    async for _event in chat.stream("reward-thread", "hello"):
        pass
    await hook.settled()

    publishes = events.calls_for("events_publish")
    assert len(publishes) == 1
    args, envelope = publishes[0]["arguments"], publishes[0]["envelope"]
    assert args["event_type"] == "chat.turn.completed"
    assert set(args["payload"]) == _PAYLOAD_KEYS
    payload = args["payload"]
    assert payload["run_id"].startswith("chat-")
    assert payload["agent_id"] == DEFAULT_AGENT_ID
    assert payload["input_summary"] == "hello"
    assert payload["output_summary"] == "humans reply"
    assert payload["idempotency_key"] == f"chat-turn:{payload['run_id']}"
    # No identity leakage (S5 landing-zone discipline).
    assert set(envelope) <= {"tenant_id", "principal_id", "session_id"}
    assert not {"tenant_id", "principal_id", "owner_id", "user_id"} & set(payload)


async def test_invoke_turn_emits_chat_turn_completed() -> None:
    """The non-stream invoke() path binds the invocation too, so it feeds
    the reward circuit as well (exactly one emission per idempotency key)."""
    chat = _chat(RepliedModel())
    events = EventsToolFake()
    hook = _hook(chat, events)

    result = await chat.invoke("invoke-reward-thread", "hi")
    await hook.settled()

    assert result.status == "completed"
    assert len(events.calls_for("events_publish")) == 1


async def test_replayed_invocation_emits_no_duplicate() -> None:
    """A replayed AfterInvocationEvent for the SAME run probes the events
    idempotency surface first and produces zero additional emissions."""
    chat = _chat(RepliedModel())
    events = EventsToolFake()
    hook = _hook(chat, events)

    async for _event in chat.stream("replay-thread", "hello"):
        pass
    await hook.settled()
    assert len(events.calls_for("events_publish")) == 1
    run_id = events.payloads[0]["run_id"]

    # Replay: re-dispatch the same event through the agent's REAL hook
    # registry with the invocation re-bound onto the original run_id.
    agent = await chat._threads.get_or_build(
        "replay-thread", DEFAULT_AGENT_ID, _fresh_agent(chat))
    token = _CURRENT_INVOCATION.set(SimpleNamespace(
        invocation_id=run_id, agent_id=DEFAULT_AGENT_ID, prompt="hello",
        tenant_id=None, owner_id=None, thread_id="replay-thread",
    ))
    try:
        event = AfterInvocationEvent(agent=agent, invocation_state={},
                                     result=SimpleNamespace(stop_reason="end_turn"))
        await agent.hooks.invoke_callbacks_async(event)
    finally:
        _CURRENT_INVOCATION.reset(token)
    await hook.settled()

    assert len(events.calls_for("events_publish")) == 1
    assert events.calls_for("events_query_events")  # probe before publish


async def test_failed_turn_never_emits() -> None:
    """strands fires the terminal AfterInvocationEvent from a ``finally``
    even when the loop died: ``result`` is None while the durable
    transcript still holds the PREVIOUS turn's assistant reply — emitting
    would score a never-completed turn and double-score that prior turn.
    The failed dispatch must produce zero activity on the events surface."""
    chat = _chat(RepliedModel())
    events = EventsToolFake()
    hook = _hook(chat, events)

    async for _event in chat.stream("failed-thread", "hello"):
        pass  # warm the thread agent + durable transcript (one real emit)
    await hook.settled()
    baseline = len(events.calls)
    assert events.payloads[0]["output_summary"] == "humans reply"

    agent = await chat._threads.get_or_build(
        "failed-thread", DEFAULT_AGENT_ID, _fresh_agent(chat))
    token = _CURRENT_INVOCATION.set(SimpleNamespace(
        invocation_id="chat-failed", agent_id=DEFAULT_AGENT_ID, prompt="boom",
        tenant_id=None, owner_id=None, thread_id="failed-thread",
    ))
    try:
        # Result-less terminal event == the turn never completed:
        event = AfterInvocationEvent(agent=agent, invocation_state={}, result=None)
        await agent.hooks.invoke_callbacks_async(event)
    finally:
        _CURRENT_INVOCATION.reset(token)
    await hook.settled()

    assert len(events.calls) == baseline  # no publish, no idempotency probe


def _fresh_agent(chat: StrandsChatAgent) -> Any:
    async def build() -> Any:
        raise AssertionError("replay must reuse the warmed thread agent")
    return build
