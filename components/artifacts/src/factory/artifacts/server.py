"""Artifacts MCP server composition."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .mcp import authoring, comments, deterministic, operational, organization, publish
from .runtime.runtime import ArtifactsRuntime, get_runtime


def create_tool_catalog(runtime: ArtifactsRuntime | None = None) -> Any:
    catalog = ToolCatalog("artifacts-module")
    active = runtime or get_runtime()
    deterministic.register(catalog, lambda: active)
    operational.register(catalog, lambda: active)
    organization.register(catalog, lambda: active)
    comments.register(catalog, lambda: active)
    authoring.register(catalog, lambda: active)
    publish.register(catalog, lambda: active)
    return catalog


def create_mcp_server(runtime: ArtifactsRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


__all__ = ["create_mcp_server", "create_tool_catalog"]
