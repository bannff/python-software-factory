"""MCP server for config module.

Exposes configuration operations via FastMCP with modular tool organization.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import get_runtime, ConfigRuntime
from .mcp import deterministic, operational, resources, prompts


def _register_tools(registry: Any, runtime: ConfigRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)


def create_tool_catalog(runtime: ConfigRuntime | None = None) -> Any:
    """Create the transport-neutral Config tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-config")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: ConfigRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


# MCP Contract Functions
def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for config brick."""
    return {
        "name": "config",
        "version": "1.0.0",
        "backends": ["env", "file", "ssm"],
        "features": [
            "key_value_config",
            "feature_flags",
            "environment_support",
            "secrets_reference",
            "aws_identity",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for config brick."""
    try:
        runtime = get_runtime()
        return {"healthy": True, "sources": len(runtime.sources)}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe config configuration schema."""
    return {
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": ["env", "file", "ssm"]},
                "description": "Config sources to load from",
            },
        },
    }

get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
