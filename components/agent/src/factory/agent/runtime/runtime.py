"""Factories for the single production runtime (strands default)."""
from __future__ import annotations

from typing import Any

DEFAULT_BACKEND = "strands"
DEFAULT_GRAPH_BACKEND = "strands"


class AgentRuntimeFactory:
    """Construct runtime adapters without provider fallback."""

    _backends: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, runtime_class: type) -> None:
        cls._backends[name] = runtime_class

    @classmethod
    def create_agent_runtime(cls, backend: str = DEFAULT_BACKEND) -> Any:
        from factory.agent.runtime.adapters import create_agent_adapter
        return create_agent_adapter(backend)

    @classmethod
    def create_swarm_runtime(
        cls, backend: str = DEFAULT_GRAPH_BACKEND,
    ) -> Any:
        from factory.agent.runtime.adapters import create_swarm_adapter
        return create_swarm_adapter(backend)

    @classmethod
    def create_graph_runtime(
        cls, backend: str = DEFAULT_GRAPH_BACKEND,
    ) -> Any:
        from factory.agent.runtime.adapters import create_graph_adapter
        return create_graph_adapter(backend)

    @classmethod
    def create_chat_agent(cls, backend: str = DEFAULT_BACKEND) -> Any:
        from factory.agent.runtime.adapters import create_chat_agent
        return create_chat_agent(backend)

    @classmethod
    def get_available_backends(cls) -> list[str]:
        return ["langchain", "langgraph", "strands"]


def get_default_runtime() -> tuple[Any, Any]:
    """Return the shared production Agent and bounded graph runtimes."""
    from factory.agent.runtime.adapters import (
        StrandsAgentRuntime, StrandsGraphRuntime, _scoped_client,
    )
    agents = StrandsAgentRuntime(_scoped_client())
    return agents, StrandsGraphRuntime(agents)
