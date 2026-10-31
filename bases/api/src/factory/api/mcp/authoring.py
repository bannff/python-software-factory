"""Authoring (security-gated) MCP tools for API base."""

from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator, ok

from ..core import AdapterType
from ..runtime.runtime import APIRuntime
from .contracts.models import (
    AuthoringStatusOutput,
    ConfigChangesOutput,
    EmptyInput,
    ResetRoutesOutput,
    SetConfigInput,
    SetConfigOutput,
)


def register(
    mcp: Any, get_runtime: Callable[[], APIRuntime], authoring_enabled: bool = False,
) -> None:
    """Register authoring tools with the MCP server."""

    @mcp.tool(name="api.authoring.get_status")
    @authoring_decorator(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Get authoring status for the API base."""
        adapter = get_runtime().get_adapter()
        return ok(AuthoringStatusOutput(
            enabled=authoring_enabled,
            adapter=adapter.adapter_type if hasattr(adapter, "adapter_type") else "unknown",
            available_backends=APIRuntime.available_backends(),
        ))

    @mcp.tool(name="api.authoring.set_config")
    @authoring_decorator(input_model=SetConfigInput, output_model=SetConfigOutput)
    def authoring_set_config(
        title: str | None = None, version: str | None = None,
        adapter_type: str | None = None,
    ) -> ToolResult[SetConfigOutput]:
        """Update API configuration when authoring is enabled."""
        if not authoring_enabled:
            return ok(SetConfigOutput(updated=False, error="Authoring is disabled"))
        runtime = get_runtime()
        changes = ConfigChangesOutput()
        if adapter_type:
            available = APIRuntime.available_backends()
            if adapter_type not in available:
                return ok(SetConfigOutput(
                    updated=False, requested=adapter_type,
                    error=f"Unknown adapter: {adapter_type}", available=available,
                ))
            runtime._adapter_type = AdapterType(adapter_type)
            runtime._adapter = None
            changes.adapter = adapter_type
        if title:
            changes.title = title
        if version:
            changes.version = version
        return ok(SetConfigOutput(updated=True, changes=changes))

    @mcp.tool(name="api.authoring.reset_routes")
    @authoring_decorator(input_model=EmptyInput, output_model=ResetRoutesOutput)
    def authoring_reset_routes() -> ToolResult[ResetRoutesOutput]:
        """Clear all registered routes when authoring is enabled."""
        if not authoring_enabled:
            return ok(ResetRoutesOutput(reset=False, error="Authoring is disabled"))
        runtime = get_runtime()
        count_before = len(runtime.list_routes())
        runtime._adapter = None
        return ok(ResetRoutesOutput(reset=True, routes_cleared=count_before))
