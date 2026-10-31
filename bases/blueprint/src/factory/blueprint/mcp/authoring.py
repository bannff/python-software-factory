"""Typed, security-gated Blueprint authoring MCP tools."""
from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring

from .authoring_contracts import UpdateServiceUrlInput, UpdateServiceUrlOutput
from ..runtime.runtime import BlueprintRuntime


def register(mcp: Any, get_runtime: Callable[[], BlueprintRuntime]) -> None:
    """Register authoring tools with strict public contracts."""

    @mcp.tool(name="blueprint_update_service_url")
    @authoring(input_model=UpdateServiceUrlInput, output_model=UpdateServiceUrlOutput)
    def blueprint_update_service_url(service_name: str, url: str) -> ToolResult[UpdateServiceUrlOutput]:
        """Update a process-local service URL in the runtime registry."""
        get_runtime().update_service_url(service_name, url)
        return {"updated": True, "service": service_name, "url": url}
