"""MCP server for worker base."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import WorkerRuntime, get_runtime
from .mcp import deterministic, operational, authoring, resources, prompts
from factory.mcp_utils.server import make_lazy_runner


def _register_tools(registry: Any, runtime: WorkerRuntime, enable_authoring: bool) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)
    authoring.register(registry, get_current, authoring_enabled=enable_authoring)


def create_tool_catalog(
    runtime: WorkerRuntime | None = None, enable_authoring: bool = False,
) -> Any:
    """Create the transport-neutral Worker tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-worker")
    _register_tools(catalog, active_runtime, enable_authoring)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(
    runtime: WorkerRuntime | None = None, enable_authoring: bool = False,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, enable_authoring)


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
