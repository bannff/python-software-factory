"""Row 61 — stop a running turn from outside the session (cancel_thread seam)."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


class SlowModel(BaseChatModel):
    """Streams one chunk, then blocks until cancelled or released."""

    gate: Any = Field(default=None, exclude=True)

    @property
    def _llm_type(self) -> str:
        return "slow-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "SlowModel":
        del tools, kwargs
        return self

    def _generate(self, messages: list[Any], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        del messages, stop, run_manager, kwargs
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="done"))])

    async def _astream(self, messages: list[Any], stop=None, run_manager=None, **kwargs: Any):
        del messages, stop, run_manager, kwargs
        yield ChatGenerationChunk(message=AIMessageChunk(content="partial"))
        await asyncio.sleep(60)  # never resolves on its own; only cancellation ends this

    def _stream(self, messages: list[Any], stop=None, run_manager=None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        del messages, stop, run_manager, kwargs
        yield ChatGenerationChunk(message=AIMessageChunk(content="partial"))


def _client() -> InMemoryScopedCapabilityClient:
    return InMemoryScopedCapabilityClient(CapabilityScope.create("cancel-test", set()), (), {})


async def _drain_until_cancelled(stream: AsyncIterator[Any]) -> list[Any]:
    events = []
    try:
        async for event in stream:
            events.append(event)
    except asyncio.CancelledError:
        pass
    return events


@pytest.mark.asyncio
async def test_cancel_thread_stops_the_live_stream_for_that_thread() -> None:
    runtime = LangChainAgentRuntime(SlowModel(), _client())
    chat = LangChainChatAgent(runtime)

    task = asyncio.ensure_future(_drain_until_cancelled(
        chat.stream("thread-a", "go slow"),
    ))
    await asyncio.sleep(0.05)  # let the turn register itself before cancelling
    cancelled = await chat.cancel("thread-a")
    await asyncio.wait_for(task, timeout=5)

    assert cancelled is True
    assert "thread-a" not in runtime._active_threads


@pytest.mark.asyncio
async def test_cancel_thread_is_scoped_and_does_not_touch_other_threads() -> None:
    runtime = LangChainAgentRuntime(SlowModel(), _client())
    chat = LangChainChatAgent(runtime)

    task_a = asyncio.ensure_future(_drain_until_cancelled(chat.stream("thread-a", "go")))
    task_b = asyncio.ensure_future(_drain_until_cancelled(chat.stream("thread-b", "go")))
    await asyncio.sleep(0.05)

    cancelled = await chat.cancel("thread-a")
    assert cancelled is True
    assert "thread-b" in runtime._active_threads  # untouched

    await chat.cancel("thread-b")
    await asyncio.wait_for(task_a, timeout=5)
    await asyncio.wait_for(task_b, timeout=5)


@pytest.mark.asyncio
async def test_cancel_thread_reports_false_when_nothing_is_running() -> None:
    runtime = LangChainAgentRuntime(SlowModel(), _client())
    chat = LangChainChatAgent(runtime)

    cancelled = await chat.cancel("thread-idle")
    assert cancelled is False
