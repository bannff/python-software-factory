"""FastMCP server interface for the logger brick.

Public MCP surface only. Tool definitions live in mcp/{deterministic,
operational,authoring}.py per brick-anatomy.md.
"""

from __future__ import annotations

from typing import Any

from factory.logger.runtime.runtime import LoggerRuntime
from factory.logger.mcp import (
    deterministic,
    operational,
    authoring,
    register_resources,
    register_prompts,
)
from factory.mcp_utils.server import make_lazy_runner


def _register_tools(registry: Any, runtime: LoggerRuntime) -> None:
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime)


def create_tool_catalog(runtime: LoggerRuntime | None = None) -> Any:
    """Create the transport-neutral Logger tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or LoggerRuntime()
    catalog = ToolCatalog("logger-module")
    _register_tools(catalog, active_runtime)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: LoggerRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


get_mcp_server, main = make_lazy_runner(create_mcp_server)


if __name__ == "__main__":
    main()
