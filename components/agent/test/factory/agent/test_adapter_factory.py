"""Tests for runtime factory selection (strands default, langchain dormant)."""
from __future__ import annotations

import pytest

from factory.agent.runtime.adapters import (
    LangChainAgentRuntime,
    LangGraphRuntime,
    MemoryAgentRuntime,
    MemoryGraphRuntime,
    MemorySwarmRuntime,
    MemoryToolLoader,
    create_agent_adapter,
    create_graph_adapter,
    create_swarm_adapter,
    create_tool_loader,
)
from factory.agent.runtime.runtime import (
    AgentRuntimeFactory,
    DEFAULT_BACKEND,
    DEFAULT_GRAPH_BACKEND,
    get_default_runtime,
)
from factory.mcp_utils.runtime.scoped_capability_client import (
    InMemoryScopedCapabilityClient,
)
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope


@pytest.fixture
def native_runtime_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the native scoped-capability seam instead of a global aggregator."""
    from factory.agent.runtime import adapters
    from factory.agent.runtime.adapters import langchain_model

    def client() -> InMemoryScopedCapabilityClient:
        return InMemoryScopedCapabilityClient(
            CapabilityScope.create("factory-test", set()), (), {},
        )

    monkeypatch.setattr(adapters, "_scoped_client", client)
    monkeypatch.setattr(langchain_model, "build_langchain_chat_model", lambda _: object())


def test_memory_adapters_remain_explicit_test_doubles() -> None:
    assert isinstance(create_agent_adapter("memory"), MemoryAgentRuntime)
    assert isinstance(create_swarm_adapter("memory"), MemorySwarmRuntime)
    assert isinstance(create_graph_adapter("memory"), MemoryGraphRuntime)
    assert isinstance(create_tool_loader("memory"), MemoryToolLoader)


def test_default_adapters_are_current_strands_runtimes(
    native_runtime_seams: None,
) -> None:
    from factory.agent.runtime.adapters import (
        StrandsAgentRuntime, StrandsGraphRuntime,
    )

    assert isinstance(create_agent_adapter(), StrandsAgentRuntime)
    assert isinstance(create_swarm_adapter(), StrandsGraphRuntime)
    assert isinstance(create_graph_adapter(), StrandsGraphRuntime)


def test_invalid_adapter_type() -> None:
    with pytest.raises(ValueError, match="unknown agent runtime adapter"):
        create_agent_adapter("invalid")


def test_runtime_factory_defaults(native_runtime_seams: None) -> None:
    from factory.agent.runtime.adapters import (
        StrandsAgentRuntime, StrandsGraphRuntime,
    )

    assert DEFAULT_BACKEND == "strands"
    assert DEFAULT_GRAPH_BACKEND == "strands"
    assert isinstance(
        AgentRuntimeFactory.create_agent_runtime(), StrandsAgentRuntime,
    )
    assert isinstance(
        AgentRuntimeFactory.create_swarm_runtime(), StrandsGraphRuntime,
    )
    assert isinstance(
        AgentRuntimeFactory.create_graph_runtime(), StrandsGraphRuntime,
    )
    assert AgentRuntimeFactory.get_available_backends() == [
        "langchain", "langgraph", "strands",
    ]


def test_get_default_runtime_shares_strands_agent_with_graph(
    native_runtime_seams: None,
) -> None:
    from factory.agent.runtime.adapters import (
        StrandsAgentRuntime, StrandsGraphRuntime,
    )

    agent_runtime, graph_runtime = get_default_runtime()
    assert isinstance(agent_runtime, StrandsAgentRuntime)
    assert isinstance(graph_runtime, StrandsGraphRuntime)
    assert graph_runtime._agents is agent_runtime
