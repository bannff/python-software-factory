"""Native MCP v2 server for API base.

Exposes API capabilities through the framework-neutral tool catalog.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import make_lazy_runner

from .runtime.runtime import get_runtime, APIRuntime
from .mcp import deterministic, operational, authoring, resources, prompts


def _register_tools(registry: Any, runtime: APIRuntime, enable_authoring: bool) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current, authoring_enabled=enable_authoring)


def create_tool_catalog(
    runtime: APIRuntime | None = None, enable_authoring: bool = False,
) -> Any:
    """Create the transport-neutral API tool catalog."""
    from factory.mcp_utils.interface import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-api")
    _register_tools(catalog, active_runtime, enable_authoring)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(
    runtime: APIRuntime | None = None,
    enable_authoring: bool = False,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, enable_authoring)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for api base."""
    return {
        "name": "api",
        "version": "1.0.0",
        "backends": ["rest", "graphql"],
        "features": ["rest_api", "graphql_api", "openapi_schema", "route_introspection"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for api base."""
    return {"healthy": True, "adapter": "rest"}


def describe_config_schema() -> dict[str, Any]:
    """Describe api configuration schema."""
    return {
        "type": "object",
        "properties": {
            "adapter": {"type": "string", "enum": ["rest", "graphql"]},
            "port": {"type": "integer", "description": "API port"},
        },
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
