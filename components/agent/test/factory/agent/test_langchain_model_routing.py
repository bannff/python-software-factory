"""Per-session model isolation and targeted refresh tests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_utils.interface import CapabilityScope


class EmptyCapabilities:
    scope = CapabilityScope.create("model-routing-test", [])

    async def list_capabilities(self):
        return ()

    async def close(self):
        return None


def request(runtime, invocation_id: str, model_id: str) -> RuntimeInvocation:
    return RuntimeInvocation(
        invocation_id=invocation_id,
        agent_id="companion-x-default",
        prompt="test",
        capability_scope_digest=runtime.capability_scope_digest,
        model_id=model_id,
    )


@pytest.mark.asyncio
async def test_concurrent_model_ids_build_distinct_models_and_graphs(monkeypatch) -> None:
    created: list[tuple[object, object]] = []

    def create_agent(model, tools, **kwargs):
        graph = object()
        created.append((model, graph))
        return graph

    import langchain.agents
    monkeypatch.setattr(langchain.agents, "create_agent", create_agent)
    built: dict[str, object] = {}

    def builder(model_id: str):
        built[model_id] = SimpleNamespace(model_id=model_id)
        return built[model_id]

    runtime = LangChainAgentRuntime(
        SimpleNamespace(model_id="default"), EmptyCapabilities(),
        model_id="default", model_builder=builder,
    )
    first, second = await asyncio.gather(
        runtime._graph(request(runtime, "one", "openai-compat/one")),
        runtime._graph(request(runtime, "two", "openai-compat/two")),
    )
    assert first is not second
    assert {model.model_id for model, _ in created} == {
        "openai-compat/one", "openai-compat/two",
    }
    assert await runtime._graph(request(runtime, "again", "openai-compat/one")) is first
    await runtime.close()


@pytest.mark.asyncio
async def test_targeted_refresh_rebuilds_only_selected_model_graph(monkeypatch) -> None:
    import langchain.agents
    monkeypatch.setattr(
        langchain.agents, "create_agent",
        lambda model, tools, **kwargs: SimpleNamespace(model=model),
    )
    runtime = LangChainAgentRuntime(
        object(), EmptyCapabilities(), model_id="default",
        model_builder=lambda model_id: SimpleNamespace(model_id=model_id),
    )
    first_request = request(runtime, "one", "openai-compat/one")
    second_request = request(runtime, "two", "openai-compat/two")
    first = await runtime._graph(first_request)
    second = await runtime._graph(second_request)
    refreshed = SimpleNamespace(model_id="openai-compat/one-refreshed")

    runtime.refresh_model("openai-compat/one", refreshed)

    assert await runtime._graph(first_request) is not first
    assert (await runtime._graph(first_request)).model is refreshed
    assert await runtime._graph(second_request) is second
    await runtime.close()


def test_runtime_invocation_rejects_invalid_model_id() -> None:
    with pytest.raises(ValueError, match="model_id"):
        RuntimeInvocation("run", "agent", "task", "scope", model_id="   ")


@pytest.mark.asyncio
async def test_chat_refresh_targets_request_model_id(monkeypatch) -> None:
    from factory.agent.runtime.adapters import aws_creds
    from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
    from factory.agent.runtime.runtime_contracts import RuntimeResult

    class Runtime:
        capability_scope_digest = "scope"
        calls = 0
        refreshed = None

        async def invoke(self, request):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("ExpiredTokenException")
            return RuntimeResult(request.invocation_id, "ok", "completed")

        def refresh_model(self, model_id, model):
            self.refreshed = (model_id, model)

    runtime = Runtime()
    monkeypatch.setattr(aws_creds, "force_refresh", lambda: None)
    built: list[str] = []

    def builder(model_id: str):
        built.append(model_id)
        return f"fresh:{model_id}"

    chat = LangChainChatAgent(runtime, builder, model_id="bedrock/model")
    result = await chat.invoke("thread", "hello")

    assert result.output == "ok"
    assert built == ["bedrock/model"]
    assert runtime.refreshed == ("bedrock/model", "fresh:bedrock/model")
