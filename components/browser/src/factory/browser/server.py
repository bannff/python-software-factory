"""Native MCP v2 server interface exposing browser tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .runtime.runtime import BrowserRuntime
from .mcp import deterministic, operational, authoring, register_resources, register_prompts


ENGINE_ENV = "FACTORY_BROWSER_ADAPTER"
ENGINES = ("mock", "cdp")


def selected_engine() -> str:
    """Process-wide engine choice; mirrors FACTORY_SECURITY_ADAPTER's composition rail."""
    import os
    value = os.environ.get(ENGINE_ENV, "mock").strip().lower()
    return value if value in ENGINES else "mock"


def _runtime(runtime: BrowserRuntime | None) -> BrowserRuntime:
    if runtime is not None:
        return runtime
    if selected_engine() == "cdp":
        from .runtime.adapters.cdp import CDPAdapter
        return BrowserRuntime(CDPAdapter())
    from .runtime.adapters.mock import MockAdapter
    return BrowserRuntime(MockAdapter())


def _register_tools(registry: Any, runtime: BrowserRuntime, config_dir: Path | None) -> None:
    enable_authoring = authoring_enabled()
    manager = AuthoringManager(config_dir or Path.cwd()) if enable_authoring else None
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime, manager)


def create_tool_catalog(
    runtime: BrowserRuntime | None = None, config_dir: Path | None = None,
) -> Any:
    """Create the transport-neutral Browser tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = _runtime(runtime)
    catalog = ToolCatalog("browser-module")
    _register_tools(catalog, active_runtime, config_dir)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    return catalog


def create_mcp_server(
    runtime: BrowserRuntime | None = None,
    config_dir: Path | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, config_dir)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for browser brick."""
    return {
        "name": "browser",
        "version": "0.1.0",
        "adapters": list(ENGINES),
        "features": [
            "browser_automation",
            "page_navigation",
            "element_interaction",
            "screenshot_capture",
            "javascript_execution",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for browser brick."""
    return {"healthy": True, "adapter": selected_engine()}


def describe_config_schema() -> dict[str, Any]:
    """Describe browser configuration schema."""
    return {
        "type": "object",
        "properties": {
            "headless": {"type": "boolean", "default": True},
            "timeout_ms": {"type": "integer", "default": 30000},
            "viewport_width": {"type": "integer", "default": 1280},
            "viewport_height": {"type": "integer", "default": 720},
        },
    }
