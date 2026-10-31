"""MCP server for blueprint base.

Exposes infrastructure configuration, CDK generation, and CI/CD
pipeline generation through the framework-neutral native MCP v2 catalog.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime import get_runtime, BlueprintRuntime
from .runtime.deploy.generator import DeployGenerator
from .mcp import deterministic, resources, prompts, operational, authoring


def _register_tools(registry: Any, runtime: BlueprintRuntime) -> None:
    get_current = lambda: runtime
    get_generator = lambda: DeployGenerator()
    deterministic.register(registry, get_current)
    operational.register(registry, get_generator, get_current)
    authoring.register(registry, get_current)


def create_tool_catalog(runtime: BlueprintRuntime | None = None) -> Any:
    """Create the transport-neutral Blueprint tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-blueprint")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: BlueprintRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for blueprint base."""
    return {
        "name": "blueprint",
        "version": "2.0.0",
        "backends": ["yaml", "json"],
        "features": [
            "service_discovery", "system_configuration", "orchestration",
            "cdk_generation", "pipeline_generation",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for blueprint base."""
    return {"healthy": True, "services": 0}


def describe_config_schema() -> dict[str, Any]:
    """Describe blueprint configuration schema."""
    return {
        "type": "object",
        "properties": {
            "config_dir": {"type": "string", "description": "Configuration directory"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
