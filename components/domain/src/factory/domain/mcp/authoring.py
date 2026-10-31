"""Authoring (security-gated) MCP tools for the domain brick."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.decorators import authoring
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from ..runtime.models import PresentationManifest
from .contracts import (
    CreateManifestInput, ManifestInput, ManifestMutationOutput, PresentationManifestInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import DomainRuntime


def register(mcp: Any, runtime: "DomainRuntime") -> None:
    """Register authoring tools."""

    @typed_tool(mcp)
    @authoring(input_model=CreateManifestInput, output_model=ManifestMutationOutput)
    def domain_create_manifest(manifest: PresentationManifestInput) -> ToolResult[ManifestMutationOutput]:
        """Create (or update) a user presentation manifest."""
        try:
            parsed = PresentationManifest.model_validate(manifest)
        except Exception as error:  # domain-invalid input is normal result data
            return ok(ManifestMutationOutput(ok=False, error=str(error)))
        runtime.create_manifest(parsed)
        return ok(ManifestMutationOutput(ok=True, domain_id=parsed.domain_id))

    @typed_tool(mcp)
    @authoring(input_model=ManifestInput, output_model=ManifestMutationOutput)
    def domain_delete_manifest(domain_id: str) -> ToolResult[ManifestMutationOutput]:
        """Delete a user presentation manifest by domain_id."""
        if not runtime.delete_manifest(domain_id):
            return ok(ManifestMutationOutput(
                ok=False, error=f"Manifest not found: {domain_id}",
            ))
        return ok(ManifestMutationOutput(ok=True, domain_id=domain_id, deleted=True))
