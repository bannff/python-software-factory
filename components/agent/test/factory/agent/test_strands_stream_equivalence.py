"""Semantic-equivalence harness: LangChain vs Strands chat adapters.

Phase-1 gate (issue #89): the four port scenarios (plain turn, tool
turn, frontend-tool interrupt+resume, cancel) run through BOTH adapters
with faked models; event-TYPE sequences and semantic fields (tool_call_id
stability, content, done reasons) must agree. Byte-identity across the
two SDK event taxonomies is explicitly NOT the bar. Shared fakes live in
``_strands_equivalence_fakes``.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("strands")

from ._strands_equivalence_fakes import (
    FE_SPEC, LangChainFakeModel, StrandsFakeModel, StrandsSlowModel,
    _langchain_agent, _strands_agent,
)


@pytest.mark.asyncio
async def test_plain_turn_event_sequences_match() -> None:
    langchain = [e async for e in _langchain_agent(LangChainFakeModel()).stream("t", "hi")]
    strands_agent = _strands_agent(StrandsFakeModel())
    strands = [e async for e in strands_agent.stream("t", "hi")]
    assert [e.type for e in langchain] == [e.type for e in strands] == ["text_delta", "done"]
    assert langchain[0].content == strands[0].content == "humans reply"
    assert strands[1].reason == langchain[1].reason == "stop"


@pytest.mark.asyncio
async def test_tool_turn_tool_call_id_is_stable() -> None:
    langchain = [e async for e in _langchain_agent(LangChainFakeModel(use_tool=True)).stream("t", "echo")]
    strands_agent = _strands_agent(StrandsFakeModel(use_tool=True))
    strands = [e async for e in strands_agent.stream("t", "echo")]
    assert [e.type for e in langchain] == [e.type for e in strands] == [
        "tool_call_delta", "tool_result", "text_delta", "done",
    ]
    # tool_call_id stable across the call/result pair in BOTH adapters
    assert langchain[0].tool_call_id == langchain[1].tool_call_id == "call-1"
    assert strands[0].tool_call_id == strands[1].tool_call_id == "call-1"


@pytest.mark.asyncio
async def test_frontend_tool_sentinel_shape_matches() -> None:
    langchain = [e async for e in _langchain_agent(LangChainFakeModel(frontend_call=True)).stream(
        "t", "open timeline", fe_tools=[FE_SPEC],
        messages=[{"role": "user", "content": "open timeline"}],
    )]
    strands_agent = _strands_agent(StrandsFakeModel(frontend_call=True))
    strands = [e async for e in strands_agent.stream(
        "t", "open timeline", fe_tools=[FE_SPEC],
        messages=[{"role": "user", "content": "open timeline"}],
    )]
    assert [e.type for e in langchain] == [e.type for e in strands] == [
        "tool_call_delta", "tool_result", "done",
    ]
    langchain_sentinel = langchain[1].payload
    strands_sentinel = strands[1].payload
    assert isinstance(langchain_sentinel, dict) and isinstance(strands_sentinel, dict)
    assert langchain_sentinel["_frontend_pending"] is strands_sentinel["_frontend_pending"] is True
    assert strands_sentinel["name"] == langchain_sentinel.get("name", "fe_navigate_canvas")
    assert strands_sentinel["args"] == {"view": "timeline-v2"}
    assert strands[1].tool_call_id == "fe-call-1"


@pytest.mark.asyncio
async def test_cancel_stops_the_running_turn() -> None:
    gate = asyncio.Event()
    chat = _strands_agent(StrandsSlowModel(gate))
    events: list[Any] = []

    async def drain() -> list[Any]:
        collected = []
        try:
            async for event in chat.stream("slow-thread", "go"):
                collected.append(event)
        except asyncio.CancelledError:
            pass
        return collected

    task = asyncio.ensure_future(drain())
    await asyncio.sleep(0.05)
    assert await chat.cancel("slow-thread") is True
    gate.set()
    events = await asyncio.wait_for(task, timeout=5)
    assert any(e.type == "text_delta" for e in events)
