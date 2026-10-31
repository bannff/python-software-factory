"""MCP server factory for the session brick."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .mcp import (
    active_checkpoint, authoring, completion, deletion, deterministic, folder, fork,
    operational, pinned_messages, session_stop, steering, summary, tagging,
    register_prompts, register_resources,
)
from .runtime.runtime import SessionRuntime, get_runtime


def create_tool_catalog(runtime: SessionRuntime | None = None) -> Any:
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-session")
    current = lambda: runtime
    deterministic.register(catalog, current)
    operational.register(catalog, current)
    deletion.register(catalog, current)
    fork.register(catalog, current)
    active_checkpoint.register(catalog, current)
    summary.register(catalog, current)
    folder.register(catalog, current)
    steering.register(catalog, current)
    session_stop.register(catalog, current)
    tagging.register(catalog, current)
    pinned_messages.register(catalog, current)
    completion.register(catalog, current)
    authoring.register(catalog, current)
    register_resources(catalog, current)
    register_prompts(catalog, current)
    return catalog


def create_mcp_server(runtime: SessionRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
