"""Devtools MCP server composition."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .mcp import authoring, deterministic, operational
from .runtime.runtime import DevtoolsRuntime, get_runtime


def create_tool_catalog(runtime: DevtoolsRuntime | None = None) -> Any:
    active = runtime or get_runtime()
    catalog = ToolCatalog("devtools-module")
    deterministic.register(catalog, active)
    operational.register(catalog, active)
    authoring.register(catalog, active)
    return catalog


def create_mcp_server(runtime: DevtoolsRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog"]
