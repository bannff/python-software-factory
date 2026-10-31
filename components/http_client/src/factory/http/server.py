"""HTTP MCP server - exposes HTTP client operations via FastMCP."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import get_runtime, HTTPRuntime
from .mcp import deterministic, operational, resources, prompts


def _register_tools(registry: Any, runtime: HTTPRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)


def create_tool_catalog(runtime: HTTPRuntime | None = None) -> Any:
    """Create the transport-neutral HTTP tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-http")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: HTTPRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


# MCP Contract Functions
def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for http brick."""
    return {
        "name": "http",
        "version": "1.0.0",
        "backends": ["httpx", "aiohttp"],
        "features": [
            "http_requests",
            "retry_logic",
            "rate_limiting",
            "auth_headers",
            "timeout_handling",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for http brick."""
    try:
        runtime = get_runtime()
        return {"healthy": True, "backend": runtime.backend_name}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe http configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {"type": "string", "enum": ["httpx", "aiohttp"]},
            "timeout": {"type": "integer", "description": "Default timeout in seconds"},
            "max_retries": {"type": "integer", "description": "Max retry attempts"},
        },
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
