"""MCP server for test module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from factory.mcp_utils.server import make_lazy_runner

from .runtime.runtime import TestRuntime
from .mcp import deterministic, operational, authoring, resources, prompts


def _surface(runtime: TestRuntime | None = None) -> tuple[TestRuntime, Path]:
    return runtime or TestRuntime.from_env(), Path(os.environ.get("TEST_CONFIG_DIR", "./config"))


def _register_tools(registry: Any, runtime: TestRuntime, config_dir: Path) -> None:
    get_current = lambda: runtime
    get_config_dir = lambda: config_dir
    deterministic.register(registry, get_current, get_config_dir)
    operational.register(registry, get_current)
    authoring.register(registry, get_current, get_config_dir)


def create_tool_catalog(runtime: TestRuntime | None = None) -> Any:
    """Create the transport-neutral Test tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime, config_dir = _surface(runtime)
    catalog = ToolCatalog("test-module")
    _register_tools(catalog, active_runtime, config_dir)
    get_current = lambda: active_runtime
    get_config_dir = lambda: config_dir
    resources.register(catalog, get_current, get_config_dir)
    prompts.register(catalog, get_current, get_config_dir)
    return catalog


def create_mcp_server(runtime: TestRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
