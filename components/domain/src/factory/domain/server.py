"""Public MCP surface for the domain brick."""
from __future__ import annotations

from typing import Any

from .mcp import (
    register_authoring, register_deterministic, register_operational,
    register_prompts, register_resources,
)
from .runtime.runtime import DomainRuntime


def get_runtime() -> DomainRuntime:
    """Create a default DomainRuntime with in-memory adapters."""
    return DomainRuntime()


def _register_tools(registry: Any, runtime: DomainRuntime) -> None:
    register_deterministic(registry, runtime)
    register_operational(registry, runtime)
    register_authoring(registry, runtime)


def create_tool_catalog(runtime: DomainRuntime | None = None) -> Any:
    """Create the transport-neutral typed Domain catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    catalog = ToolCatalog("domain-module")
    active = runtime or get_runtime()
    _register_tools(catalog, active)
    register_resources(catalog, active)
    register_prompts(catalog, active)
    return catalog


def create_mcp_server(runtime: DomainRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)
