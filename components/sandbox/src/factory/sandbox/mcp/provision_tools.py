"""Typed manifest-provisioning MCP tools for the Sandbox brick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import Field

from factory.mcp_utils.interface import deterministic, ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult
from .conversions import (
    to_mcp_manifest, to_mcp_plan, to_mcp_result, to_runtime_manifest, to_runtime_plan,
)
from .provision_models import (
    ApplyProvisionRequest, ApplyProvisionResult, ManifestRequest,
    ManifestValidationResult, PlanProvisionResult, SandboxManifestDTO, SandboxProvisionPlan,
)

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed manifest validation, planning, and application tools."""

    @mcp.tool(name="sandbox.validate_manifest")
    @deterministic(input_model=ManifestRequest, output_model=ManifestValidationResult)
    async def validate_manifest(manifest: SandboxManifestDTO = Field(...)) -> ToolResult[ManifestValidationResult]:
        """Validate a sandbox manifest."""
        from ..runtime.provisioning import validate_manifest as validate
        raw = await validate(to_runtime_manifest(SandboxManifestDTO.model_validate(manifest)).model_dump())
        raw_manifest = raw.get("manifest")
        return ok(ManifestValidationResult(
            valid=raw["valid"], errors=raw.get("errors", []),
            manifest=to_mcp_manifest(raw_manifest) if raw_manifest else None,
            summary=raw.get("summary"),
        ))

    @mcp.tool(name="sandbox.plan_provision")
    @operational(input_model=ManifestRequest, output_model=PlanProvisionResult)
    async def plan_provision(manifest: SandboxManifestDTO = Field(...)) -> ToolResult[PlanProvisionResult]:
        """Generate an ordered provision plan without applying it."""
        from ..runtime.provisioning import plan_provision as plan
        raw = await plan(to_runtime_manifest(SandboxManifestDTO.model_validate(manifest)).model_dump())
        from ..runtime.manifest import ProvisionPlan
        return ok(PlanProvisionResult(plan=to_mcp_plan(ProvisionPlan.model_validate(raw))))

    @mcp.tool(name="sandbox.apply_provision")
    @operational(input_model=ApplyProvisionRequest, output_model=ApplyProvisionResult)
    async def apply_provision(
        env_id: str = Field(min_length=1, max_length=256),
        plan: SandboxProvisionPlan = Field(...),
    ) -> ToolResult[ApplyProvisionResult]:
        """Apply a provision plan to a sandbox environment."""
        from ..runtime.manifest import ProvisionResult
        from ..runtime.provisioning import apply_provision as apply

        async def execute(eid: str, command: str, timeout: int = 300):
            return (await runtime.execute(eid, command, timeout)).model_dump()

        result = await apply(
            env_id, to_runtime_plan(SandboxProvisionPlan.model_validate(plan)).model_dump(), execute,
        )
        from ..runtime.manifest import ProvisionResult
        return ok(ApplyProvisionResult(result=to_mcp_result(ProvisionResult.model_validate(result))))
