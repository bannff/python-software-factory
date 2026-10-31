"""Graph runtime factory for portable KnowledgeGraph adapters."""
from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from .ports import KnowledgeGraph

logger = logging.getLogger(__name__)


class GraphRuntime:
    """Factory for portable graph adapter instances."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._graphs: dict[str, KnowledgeGraph] = {}
        self._default_backend = self._config.get("default_backend", "persistent_networkx")

    @property
    def default_backend(self) -> str:
        return self._default_backend

    def get_graph(self, backend: str = "persistent_networkx", **kwargs: Any) -> KnowledgeGraph:
        """Get or create a configured portable graph adapter."""
        key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._graphs:
            self._graphs[key] = self._create_graph(backend, **kwargs)
        return self._graphs[key]

    def _create_graph(self, backend: str, **kwargs: Any) -> KnowledgeGraph:
        if backend == "persistent_networkx":
            from .adapters.persistent_networkx import PersistentNetworkXGraph
            return PersistentNetworkXGraph(**kwargs)
        if backend == "networkx":
            from .adapters.networkx_adapter import NetworkXGraph
            return NetworkXGraph(**kwargs)
        if backend == "neo4j":
            from factory.mcp_utils.interface import get_neo4j_config
            from .adapters.neo4j_adapter import Neo4jGraph
            return Neo4jGraph(**get_neo4j_config(), **kwargs)
        raise SafeDiagnostic(
            f"Unknown graph backend: {backend}. Available: {self.available_backends()}"
        )

    def health_check(self) -> dict[str, Any]:
        """Check health of initialized graph adapters."""
        return {name: graph.health_check() for name, graph in self._graphs.items()}

    @staticmethod
    def available_backends() -> list[str]:
        return ["persistent_networkx", "networkx", "neo4j"]

    @staticmethod
    def provenance_backends() -> list[str]:
        """Backends with the durable Graph provenance contract."""
        return ["persistent_networkx", "networkx"]


_runtime: GraphRuntime | None = None


def get_runtime() -> GraphRuntime:
    global _runtime
    if _runtime is None:
        _runtime = GraphRuntime()
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None
