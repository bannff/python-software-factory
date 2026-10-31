"""Canonical Connections MCP server."""
from __future__ import annotations

from typing import Any

from .mcp import computer_use, tools
from .runtime.runtime import ConnectionsRuntime, get_runtime


def create_tool_catalog(runtime: ConnectionsRuntime | None = None) -> Any:
    from factory.mcp_utils.interface import ToolCatalog, set_service
    active = runtime or get_runtime()
    catalog = ToolCatalog("factory-connections")
    tools.register(catalog, lambda: active)
    computer_use.register(catalog, lambda: active)
    # Bases compose: the API attaches the gateway mount seam and triggers the
    # startup remount through these services without importing this brick's runtime.
    set_service("connections_attach_gateway", active.attach_gateway)
    set_service("connections_remount_all", active.remount_all)
    set_service("connections_store", active.store)
    return catalog


def create_mcp_server(runtime: ConnectionsRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog"]
