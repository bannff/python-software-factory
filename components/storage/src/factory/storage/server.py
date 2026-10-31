"""Storage MCP server - exposes storage operations via FastMCP."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import get_runtime, StorageRuntime
from .mcp import (
    deterministic, operational, sql_tools, graph_tools, resources, prompts,
    immutable_documents, protected_artifacts, credential_slots, owner_secrets,
)
from .mcp.views import register as register_views


def _register_tools(registry: Any, runtime: StorageRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    immutable_documents.register(registry, get_current)
    protected_artifacts.register(registry, get_current)
    credential_slots.register(registry, get_current)
    owner_secrets.register(registry, get_current)
    sql_tools.register(registry, get_current)
    graph_tools.register(registry, get_current)
    register_views(registry)


def create_tool_catalog(runtime: StorageRuntime | None = None) -> Any:
    """Create the transport-neutral Storage tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-storage")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: StorageRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


# MCP Contract Functions
def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for storage brick."""
    return {
        "name": "storage",
        "version": "1.0.0",
        "backends": {
            "blob": ["local_fs", "s3"],
            "document": ["tinydb", "mongodb", "neo4j"],
            "sql": ["sqlite", "postgres"],
            "graph": ["networkx", "neo4j"],
        },
        "features": [
            "blob_storage",
            "document_storage",
            "sql_storage",
            "graph_storage",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for storage brick."""
    try:
        runtime = get_runtime()
        return {"healthy": True, "stores": list(runtime.stores.keys())}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe storage configuration schema."""
    return {
        "type": "object",
        "properties": {
            "blob_backend": {"type": "string", "enum": ["local_fs", "s3"]},
            "document_backend": {"type": "string", "enum": ["tinydb", "mongodb"]},
            "sql_backend": {"type": "string", "enum": ["sqlite", "postgres"]},
            "graph_backend": {"type": "string", "enum": ["networkx", "neo4j"]},
        },
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
