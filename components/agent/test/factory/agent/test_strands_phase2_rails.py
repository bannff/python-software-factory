"""Phase-2 rail contract tests: approval interrupt/resume + steer.

Strands-side counterparts of the LangChain approval-resume and steering
contracts — the byte-identical ``_approval_pending`` payload, the
no-extra-model-call replay, the cancel-tool denial path, and the
next-model-boundary steer semantics. Fakes in ``_strands_rail_fakes``.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent

from ._strands_contract_fakes import NullClient
from ._strands_rail_fakes import SteerCountingModel, approval_chat


@pytest.mark.asyncio
async def test_listed_tool_pauses_with_byte_identical_approval_payload() -> None:
    """Policy-listed tool pauses with the EXACT ``_approval_pending``
    payload langchain emits, then InterruptEvent + DoneEvent(tool_use)
    in the langchain_chat event order."""
    chat, model, ctx = approval_chat()
    await ctx["seed"]()
    first = [e async for e in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
    )]
    assert [e.type for e in first] == ["tool_call_delta", "interrupt", "done"]
    interrupt = first[1]
    assert interrupt.interrupt_id == "approval-call-1"
    assert interrupt.tool == "demo_tool"
    assert interrupt.command == json.dumps({"value": "x"}, sort_keys=True, default=str)[:300]
    assert ctx["ran"] == []  # paused: the tool did NOT run
    assert model.calls == 1  # only the first model call happened
    assert all(not isinstance(getattr(e, "payload", None), dict)
               or "_frontend_pending" not in e.payload for e in first)


@pytest.mark.asyncio
async def test_approved_resume_runs_tool_once_without_extra_model_call() -> None:
    """Resume maps the re-POSTed role:'tool' entry onto the pending
    interrupt: tool runs EXACTLY once, replay makes NO fresh model call."""
    chat, model, ctx = approval_chat()
    await ctx["seed"]()
    first = [e async for e in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
    )]
    interrupt = next(e for e in first if e.type == "interrupt")

    second = [e async for e in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
        messages=[
            {"role": "user", "content": "run tool"},
            {"role": "tool", "toolCallId": interrupt.interrupt_id,
             "content": '{"approved":true}'},
        ],
    )]
    assert [e.type for e in second] == ["tool_result", "text_delta", "done"]
    assert second[1].content == "Tool completed"
    assert ctx["ran"] == ["approval-call-1"]  # exactly once
    assert model.calls == 2  # no extra model call for the replay


@pytest.mark.asyncio
async def test_denied_resume_yields_error_tool_result_completion() -> None:
    """Denial → cancel_tool → error ToolResult; the loop still completes
    cleanly so the UI renders the denial, not an error page."""
    chat, model, ctx = approval_chat()
    await ctx["seed"]()
    first = [e async for e in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
    )]
    interrupt = next(e for e in first if e.type == "interrupt")

    second = [e async for e in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
        messages=[
            {"role": "user", "content": "run tool"},
            {"role": "tool", "toolCallId": interrupt.interrupt_id,
             "content": '{"approved":false}'},
        ],
    )]
    assert [e.type for e in second] == ["tool_result", "text_delta", "done"]
    assert second[0].is_error is True
    assert ctx["ran"] == []  # the tool never executed
    assert model.calls == 2


@pytest.mark.asyncio
async def test_steer_queues_at_next_model_boundary_and_settles() -> None:
    """Guidance written mid-turn reaches the model at the NEXT model
    boundary only, and is consumed exactly once."""
    chat = StrandsChatAgent(NullClient(), lambda _mid, **_kw: None, model_id="fake")

    # Gate the model so the turn is verifiably mid-flight when steer fires.
    release = asyncio.Event()

    class GatedModel(SteerCountingModel):
        async def stream(self, messages: Any, tool_specs: Any = None,
                         system_prompt: Any = None, **kwargs: Any) -> AsyncIterator[dict]:
            if not release.is_set():
                await release.wait()
            async for event in super().stream(messages, tool_specs, system_prompt, **kwargs):
                yield event

    async def _build() -> Any:
        from strands import Agent
        return Agent(
            agent_id="companion-x-default", name="steer-thread",
            system_prompt="test", model=GatedModel(), tools=[],
            callback_handler=None, hooks=[chat._steer_hook],
        )

    await chat._threads.get_or_build("steer-thread", "companion-x-default", _build)
    agent = await chat._threads.get_or_build("steer-thread", "companion-x-default", _build)

    async def drain() -> list[Any]:
        return [e async for e in chat.stream("steer-thread", "turn one")]

    task = asyncio.ensure_future(drain())
    await asyncio.sleep(0.05)  # let the turn reach the gated model call
    assert await chat.steer("steer-thread", "s1", "prefer bullets") is not None
    release.set()
    await asyncio.wait_for(task, timeout=5)

    # The queued guidance rides turn TWO's first model call (it was queued
    # after turn one's model call had already started).
    _ = [e async for e in chat.stream("steer-thread", "turn two")]
    seen = agent.model.seen
    turn_two = seen[-1]
    assert any(
        "[steer] prefer bullets" in block for _role, blocks in turn_two for block in blocks
    ), f"guidance missing from turn two: {turn_two}"
    assert all(
        "[steer] prefer bullets" not in block
        for _role, blocks in seen[0] for block in blocks
    )
    assert chat._steer_hook._queued == {}  # settled: consumed exactly once


@pytest.mark.asyncio
async def test_steer_to_idle_thread_returns_none() -> None:
    """No active turn → nothing to steer → None (langchain semantics)."""
    model = SteerCountingModel()
    chat = StrandsChatAgent(NullClient(), lambda _mid, **_kw: model, model_id="fake")

    async def _build() -> Any:
        from strands import Agent
        return Agent(
            agent_id="companion-x-default", name="idle-thread",
            system_prompt="test", model=model, tools=[],
            callback_handler=None, hooks=[chat._steer_hook],
        )

    await chat._threads.get_or_build("idle-thread", "companion-x-default", _build)
    assert await chat.steer("idle-thread", "s1", "prefer bullets") is None
    assert chat._steer_hook._queued == {}
