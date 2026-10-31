"""Canonical Scheduler MCP server."""
from __future__ import annotations

from typing import Any

from .mcp import deterministic, migration_import, operational
from .runtime.runtime import (
    SchedulerRuntime, ensure_telemetry_retention_schedule, get_runtime,
)


def create_tool_catalog(runtime: SchedulerRuntime | None = None) -> Any:
    from factory.mcp_utils.interface import ToolCatalog
    active = runtime or get_runtime()
    catalog = ToolCatalog("factory-scheduler")
    current = lambda: active
    deterministic.register(catalog, current)
    operational.register(catalog, current)
    migration_import.register(catalog, current)
    from factory.mcp_utils.interface import set_service
    set_service("scheduler_due_runner", active.tick)
    set_service(
        "scheduler_maintenance_seeder",
        lambda: ensure_telemetry_retention_schedule(active),
    )
    return catalog


def create_mcp_server(runtime: SchedulerRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog"]
