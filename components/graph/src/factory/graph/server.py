"""MCP server for the portable Graph brick."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .mcp import authoring, deterministic, operational, prompts, resources
from .mcp._deterministic_meta import capabilities_for
from .mcp.views import register as register_views
from .runtime.runtime import GraphRuntime, get_runtime, reset_runtime as _reset_runtime
from .runtime.taxonomies.can_failure import register as register_can_failure_taxonomy
from .runtime.taxonomies.edge import register as register_edge_taxonomy
from .runtime.taxonomy_registry import get_extensions


def _surface(runtime: GraphRuntime | None = None) -> GraphRuntime:
    if runtime is None:
        from factory.mcp_utils.config_helpers import get_infra
        runtime = GraphRuntime(config={"default_backend": get_infra("graph.backend", "persistent_networkx")})
    if "can_failure" not in get_extensions():
        register_can_failure_taxonomy()
    if "edge" not in get_extensions():
        register_edge_taxonomy()
    return runtime


def _register_tools(registry: Any, runtime: GraphRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current)
    register_views(registry, runtime)


def create_tool_catalog(runtime: GraphRuntime | None = None) -> Any:
    """Create the transport-neutral Graph tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = _surface(runtime)
    catalog = ToolCatalog("factory-graph")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: GraphRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return portable Graph capabilities for local callers."""
    return capabilities_for(get_runtime())


def health_check() -> dict[str, Any]:
    """Return a compact local readiness probe."""
    health = get_runtime().health_check()
    return {"healthy": all(item.healthy for item in health.values()), "graphs": len(health)}


def describe_config_schema() -> dict[str, Any]:
    """Describe Graph configuration for local callers."""
    return {"type": "object", "properties": {"backend": {"type": "string", "enum": ["persistent_networkx", "networkx", "neo4j"]}}, "required": ["backend"]}


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
