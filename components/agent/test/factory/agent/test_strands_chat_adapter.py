"""Contract tests for the Strands chat adapter (fake strands models).

Strands counterparts of the fake-``BaseChatModel`` LangChain adapter
tests: approval resume placeholder behavior, frontend resume sentinel
shape, cancel-running-turn, invoke basic. The LangChain adapter tests
stay untouched and green — both runtimes coexist through phase 2.
Shared fakes live in ``_strands_contract_fakes``; the phase-2 approval/
steer rail fakes in ``_strands_rail_fakes``.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent
from factory.agent.runtime.models import FrontendToolSpec
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from strands import Agent

from ._strands_contract_fakes import NullClient, RepliedModel, _chat
from ._strands_equivalence_fakes import FE_SPEC, StrandsSlowModel


async def _noop_build() -> Any:
    return None


async def _fresh_build() -> Any:
    return "fresh"


@pytest.mark.asyncio
async def test_invoke_basic() -> None:
    chat = _chat(RepliedModel())
    result = await chat.invoke("invoke-thread", "hello")
    assert result.output == "humans reply"
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_invoke_preserves_thread_identity() -> None:
    chat = _chat(RepliedModel())
    first = await chat.invoke("id-thread", "one")
    second = await chat.invoke("id-thread", "two")
    assert first.output == second.output == "humans reply"
    # Same cached per-thread agent — the conversation persisted in memory.
    assert await chat._threads.get_or_build("id-thread", "companion-x-default", _noop_build) is not None


@pytest.mark.asyncio
async def test_frontend_resume_sentinel_shape() -> None:
    chat = _chat(RepliedModel("frontend"))
    first = [e async for e in chat.stream(
        "fe-thread", "open timeline", fe_tools=[FE_SPEC],
        messages=[{"role": "user", "content": "open timeline"}],
    )]
    assert [e.type for e in first] == ["tool_call_delta", "tool_result", "done"]
    assert first[1].payload["_frontend_pending"] is True
    assert first[1].payload["name"] == "fe_navigate_canvas"
    assert first[1].payload["args"] == {"view": "timeline-v2"}
    assert first[1].tool_call_id == "fe-call-1"
    # The FE stub unregisters after the turn (port contract: per-turn).
    thread_agent = await chat._threads.get_or_build("fe-thread", "companion-x-default", _noop_build)
    assert "fe_navigate_canvas" not in thread_agent.tool_registry.dynamic_tools


@pytest.mark.asyncio
async def test_cancel_running_turn() -> None:
    gate = asyncio.Event()
    chat = _chat(StrandsSlowModel(gate))

    async def drain() -> list[Any]:
        collected = []
        try:
            async for event in chat.stream("cancel-thread", "go slow"):
                collected.append(event)
        except asyncio.CancelledError:
            pass
        return collected

    task = asyncio.ensure_future(drain())
    await asyncio.sleep(0.05)
    assert await chat.cancel("cancel-thread") is True
    gate.set()
    events = await asyncio.wait_for(task, timeout=5)
    assert any(e.type == "text_delta" for e in events)


@pytest.mark.asyncio
async def test_cancel_is_false_when_nothing_is_running() -> None:
    chat = _chat(RepliedModel())
    assert await chat.cancel("idle-thread") is False


@pytest.mark.asyncio
async def test_approval_resume_placeholder_runs_listed_tool_without_interrupt() -> None:
    """Phase-2 wires the approval interrupt; phase 1's placeholder contract
    is that the turn completes and the sentinel payload shape the phase-2
    rail must emit stays the existing interrupt-event dict (unchanged
    ``langchain_stream.pending_approval_events`` contract)."""
    class DemoClient(NullClient):
        scope = CapabilityScope.create("strands-chat-test", {"demo_tool"})

        async def list_capabilities(self) -> tuple[Any, ...]:
            from factory.mcp_utils.runtime.scoped_capabilities import CapabilityDescriptor
            return (CapabilityDescriptor("demo_tool", "demo", {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }),)

        async def invoke(self, request: Any) -> Any:
            from factory.mcp_utils.runtime.scoped_capabilities import CapabilityResult
            return CapabilityResult(
                content=({"type": "text", "text": request.arguments["value"]},),
            )

    model = RepliedModel("approval")
    chat = StrandsChatAgent(
        DemoClient(), lambda _mid, **_kw: model, model_id="fake",
    )
    # Register the scoped tool the same way the persona factory projects it.
    from factory.agent.runtime.adapters.strands_agent_factory import (
        _CapabilityAgentTool,
    )
    from factory.agent.runtime.adapters.capability_policy import effective_persona_scope
    from factory.agent.runtime.personas import resolve_agent_config

    persona = resolve_agent_config("companion-x-default")
    effective = effective_persona_scope(DemoClient.scope, persona)
    tool = _CapabilityAgentTool(DemoClient(), effective, (await DemoClient().list_capabilities())[0])

    async def _seed() -> Any:
        return Agent(
            agent_id="companion-x-default",
            name="approval-thread",
            system_prompt="test",
            model=model,
            tools=[tool],
            callback_handler=None,
        )

    await chat._threads.get_or_build("approval-thread", "companion-x-default", _seed)
    events = [e async for e in chat.stream("approval-thread", "run tool")]
    assert [e.type for e in events] == ["tool_call_delta", "tool_result", "text_delta", "done"]
    assert events[2].content == "Tool completed"
    assert events[1].payload == "x"  # structured unwrap of [{"text": "x"}]


@pytest.mark.asyncio
async def test_close_drops_the_thread_agent() -> None:
    chat = _chat(RepliedModel())
    await chat.invoke("close-thread", "one")
    assert await chat._threads.get_or_build("close-thread", "companion-x-default", _noop_build) is not None
    chat.close("close-thread")
    # drop() forgets the cache: the next get_or_build rebuilds from scratch.
    rebuilt = await chat._threads.get_or_build(
        "close-thread", "companion-x-default", _fresh_build,
    )
    assert rebuilt == "fresh"
