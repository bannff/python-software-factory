"""Native MCP v2 server interface for the events brick.

Public MCP surface only. All backend wiring (memory, sqlite, aws, neo4j,
redis) lives in :class:`EventsRuntime`. See workflow brick's ``server.py``
for the canonical thin-factory pattern.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .authoring import EventsAuthoring
from .runtime.runtime import EventsRuntime
from .mcp import deterministic, operational, authoring, resources, prompts, views


def _surface(runtime: EventsRuntime | None = None) -> tuple[EventsRuntime, EventsAuthoring, Path]:
    config_dir = Path(os.environ.get("EVENTS_CONFIG_DIR", "./config"))
    return runtime or EventsRuntime.from_config_dir(config_dir), EventsAuthoring(config_dir), config_dir


def _register_tools(
    registry: Any, runtime: EventsRuntime, authoring_mgr: EventsAuthoring, config_dir: Path,
) -> None:
    get_runtime = lambda: runtime
    get_authoring = lambda: authoring_mgr
    get_config_dir = lambda: config_dir
    deterministic.register(registry, get_runtime, get_authoring, get_config_dir)
    operational.register(registry, get_runtime)
    authoring.register(registry, get_authoring, get_runtime)
    views.register(registry, runtime)


def create_tool_catalog(runtime: EventsRuntime | None = None) -> Any:
    """Create the transport-neutral Events tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime, authoring_mgr, config_dir = _surface(runtime)
    catalog = ToolCatalog("events-module")
    _register_tools(catalog, active_runtime, authoring_mgr, config_dir)
    get_runtime = lambda: active_runtime
    get_config_dir = lambda: config_dir
    resources.register(catalog, get_runtime, get_config_dir)
    prompts.register(catalog, get_runtime, get_config_dir)
    return catalog


def create_mcp_server(runtime: EventsRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for events brick."""
    return {
        "name": "events",
        "version": "1.0.0",
        "backends": ["memory", "sqlite", "aws", "neo4j", "redis"],
        "features": [
            "event_streaming", "message_bus", "pub_sub",
            "event_history", "event_replay",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for events brick."""
    try:
        config_dir = Path(os.environ.get("EVENTS_CONFIG_DIR", "./config"))
        EventsRuntime.from_config_dir(config_dir)
        return {"healthy": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe events configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {
                "type": "string",
                "enum": ["memory", "sqlite", "aws", "neo4j", "redis"],
            },
            "retention_days": {"type": "integer", "description": "Event retention"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)


if __name__ == "__main__":
    main()
