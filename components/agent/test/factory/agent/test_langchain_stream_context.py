"""Invocation context survives cross-task LangChain stream closure."""
from types import SimpleNamespace

import asyncio
import pytest
pytest.importorskip("langchain")
from langchain_core.messages import AIMessageChunk

from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_utils.interface import CapabilityScope


class EmptyCapabilities:
    scope = CapabilityScope.create("cross-context-stream", [])

    async def list_capabilities(self):
        return ()

    async def close(self):
        return None


class FakeGraph:
    async def aget_state(self, config):
        return SimpleNamespace(interrupts=())

    async def astream(self, *args, **kwargs):
        yield AIMessageChunk(content="hello"), {}


@pytest.mark.asyncio
async def test_stream_can_close_from_another_task_without_context_token_error(
    monkeypatch,
) -> None:
    runtime = LangChainAgentRuntime(object(), EmptyCapabilities())
    request = RuntimeInvocation(
        invocation_id="cross-context", agent_id="companion-x-default",
        prompt="hello", capability_scope_digest=runtime.capability_scope_digest,
        thread_id="thread",
    )

    async def graph(_request):
        return FakeGraph()

    monkeypatch.setattr(runtime, "_graph", graph)
    stream = runtime.stream(request)
    first = await anext(stream)
    assert first.kind == "text_delta"
    await asyncio.create_task(stream.aclose())
    await runtime.close()
