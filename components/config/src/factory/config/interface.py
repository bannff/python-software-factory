"""Polylith interface for config brick."""

from __future__ import annotations

from typing import Any

from .server import create_mcp_server as create_server
from .runtime import runtime


def get_infra(key: str, default: Any = None) -> Any:
    """Get an infrastructure config value via layered resolution.

    Checks InfraEnv (NEO4J_URI, GRAPH_BACKEND, etc.) then SSM
    (/art/support/*), then falls back to the provided default.

    Usage:
        backend = get_infra("memory.backend", "memory")
        uri = get_infra("neo4j.uri", "bolt://localhost:7687")
    """
    return runtime.get_runtime().get_layered(key, default)


def get_neo4j_config() -> dict[str, str]:
    """Get full Neo4j connection config via layered resolution.

    Returns:
        {"uri": ..., "user": ..., "password": ..., "database": ...}
    """
    return {
        "uri": get_infra("neo4j.uri", "bolt://localhost:7687"),
        "user": get_infra("neo4j.user", "neo4j"),
        "password": get_infra("neo4j.password", "password"),
        "database": get_infra("neo4j.database", "neo4j"),
    }


__all__ = ["create_server", "runtime", "get_infra", "get_neo4j_config"]
