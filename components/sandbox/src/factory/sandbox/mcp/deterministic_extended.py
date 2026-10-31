"""Typed deterministic derived-data MCP tools for the sandbox brick."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import Field

from factory.mcp_utils.interface import deterministic, ok, op_kind
from factory.mcp_utils.runtime.tool_result import ToolResult
from .conversions import to_mcp_environment
from .contracts import EmptyInput

from .extended_models import (
    SandboxCfnRequest, SandboxCfnResult, SandboxEnvironmentListResult,
    SandboxReconResource, SandboxSkippedReconResource,
)

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def _skipped(resources: list[SandboxReconResource]) -> list[SandboxSkippedReconResource]:
    from ..runtime.cfn_defaults import _GENERATORS

    skipped = []
    for index, resource in enumerate(resources):
        if not resource.type:
            skipped.append(SandboxSkippedReconResource(index=index, reason="missing_type"))
        elif not resource.name:
            skipped.append(SandboxSkippedReconResource(index=index, reason="missing_name"))
        elif resource.type not in _GENERATORS:
            skipped.append(SandboxSkippedReconResource(index=index, reason="unsupported_type"))
    return skipped


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed read-only and derived sandbox tools."""

    @mcp.tool(name="sandbox.list_environments")
    @deterministic(input_model=EmptyInput, output_model=SandboxEnvironmentListResult)
    @op_kind("read")
    def list_environments() -> ToolResult[SandboxEnvironmentListResult]:
        """List persisted and discovered sandbox environments."""
        environments = runtime.list_environments()
        return ok(SandboxEnvironmentListResult(
            environments=[to_mcp_environment(value) for value in environments],
            count=len(environments),
        ))

    @mcp.tool(name="sandbox.generate_cfn_from_recon")
    @deterministic(input_model=SandboxCfnRequest, output_model=SandboxCfnResult)
    @op_kind("read")
    def generate_cfn_from_recon(
        resources: list[SandboxReconResource] = Field(...),
        description: str = Field(default="Auto-generated from discovered resources", min_length=1),
    ) -> ToolResult[SandboxCfnResult]:
        """Derive a CFN template and report skipped recon entries."""
        from ..runtime.cfn_defaults import build_cfn_template

        typed_resources = [SandboxReconResource.model_validate(resource) for resource in resources]
        rows = [resource.model_dump() for resource in typed_resources]
        template = build_cfn_template(rows, description)
        return ok(SandboxCfnResult(
            template=template,
            generated_count=len(template["Resources"]),
            skipped=_skipped(typed_resources),
        ))
