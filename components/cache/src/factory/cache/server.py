"""Cache MCP server - exposes cache operations via FastMCP."""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import get_runtime, CacheRuntime
from .mcp import deterministic, operational, resources, prompts
from .mcp.views import register as register_views


def create_tool_catalog(runtime: CacheRuntime | None = None) -> Any:
    """Create the transport-neutral typed Cache tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-cache")
    get_current = lambda: runtime
    deterministic.register(catalog, get_current)
    operational.register(catalog, get_current)
    register_views(catalog)
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: CacheRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


# MCP Contract Functions
def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for cache brick."""
    return {
        "name": "cache",
        "version": "1.0.0",
        "backends": ["memory", "redis"],
        "features": [
            "key_value_cache",
            "ttl_support",
            "pattern_matching",
            "statistics",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for cache brick."""
    try:
        runtime = get_runtime()
        adapter_health = runtime.health_check()
        # Aggregate: healthy if all adapters healthy (or no adapters yet)
        all_healthy = all(h.healthy for h in adapter_health.values()) if adapter_health else True
        return {
            "healthy": all_healthy,
            "adapters": {k: {"healthy": v.healthy, "backend": v.backend} for k, v in adapter_health.items()},
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe cache configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {
                "type": "string",
                "enum": ["memory", "redis"],
                "description": "Cache backend to use",
            },
            "default_ttl": {
                "type": "integer",
                "description": "Default TTL in seconds",
            },
        },
        "required": ["backend"],
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
