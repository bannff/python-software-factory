"""Lessons MCP server composition."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.interface import set_service

from .mcp import deterministic, import_record, operational
from .runtime.runtime import LessonsRuntime, get_runtime


def create_tool_catalog(runtime: LessonsRuntime | None = None) -> Any:
    catalog = ToolCatalog("lessons-module")
    active = runtime or get_runtime()
    deterministic.register(catalog, lambda: active)
    operational.register(catalog, lambda: active)
    import_record.register(catalog, lambda: active)
    set_service("lessons_projection_reconciler", active.reconcile_projections)
    return catalog


def create_mcp_server(runtime: LessonsRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog"]
