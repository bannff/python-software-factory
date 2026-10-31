"""MCP server for blockchain module."""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import BlockchainRuntime
from .mcp import deterministic, operational, authoring, resources, prompts
from .mcp.views import register as register_views


def _register_tools(registry: Any, runtime: BlockchainRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current)
    register_views(registry, runtime)


def create_tool_catalog(runtime: BlockchainRuntime | None = None) -> Any:
    """Create the transport-neutral Blockchain tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or BlockchainRuntime()
    catalog = ToolCatalog("blockchain-module")
    _register_tools(catalog, active_runtime)
    resources.register(catalog)
    prompts.register(catalog)
    return catalog


def create_mcp_server(runtime: BlockchainRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return truthful capabilities for the active economy composition."""
    return dict(BlockchainRuntime().capabilities())


def health_check() -> dict[str, Any]:
    """Fast readiness probe for the active economy adapter."""
    return dict(BlockchainRuntime().health_check())


def describe_config_schema() -> dict[str, Any]:
    """Describe the finite trusted economy adapter configuration."""
    return BlockchainRuntime().config_schema()


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
