"""Portability MCP server composition."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .mcp import export


def create_tool_catalog() -> Any:
    catalog = ToolCatalog("portability-module")
    export.register(catalog)
    return catalog


def create_mcp_server() -> Any:
    return create_tool_catalog()


__all__ = ["create_mcp_server", "create_tool_catalog"]
