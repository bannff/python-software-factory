"""Deterministic (read-only) MCP tools for the domain brick."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import EmptyInput, GetManifestOutput, ListManifestsOutput, ManifestInput, ManifestOutput

if TYPE_CHECKING:
    from ..runtime.runtime import DomainRuntime


def register(mcp: Any, runtime: "DomainRuntime") -> None:
    """Register deterministic tools."""

    @typed_tool(mcp)
    @deterministic(input_model=ManifestInput, output_model=GetManifestOutput)
    def domain_get_manifest(domain_id: str) -> ToolResult[GetManifestOutput]:
        """Get a manifest; arbitrary domain ids total-fallback to generic."""
        manifest = ManifestOutput.model_validate(runtime.get_manifest(domain_id).model_dump())
        return ok(GetManifestOutput(manifest=manifest))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ListManifestsOutput)
    def domain_list_manifests() -> ToolResult[ListManifestsOutput]:
        """List all presentation manifests (built-ins + user-created)."""
        manifests = [ManifestOutput.model_validate(m.model_dump()) for m in runtime.list_manifests()]
        return ok(ListManifestsOutput(manifests=manifests, count=len(manifests)))
