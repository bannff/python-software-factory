"""Public lifecycle and service-only protected-artifact MCP tools."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    AuthorizationAssertion, ProtectedArtifactRef, ProtectedContentDescriptor,
    ToolResult, deterministic, fail, get_envelope, get_principal_id, operational,
    service_only,
)

from .contracts.protected_artifacts import (
    ProtectedArtifactCreateInput, ProtectedArtifactCreateOutput,
    ProtectedArtifactMaterializeOutput, ProtectedArtifactProjectOutput,
    ProtectedArtifactRefInput, ProtectedArtifactTombstoneOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime

_ERROR = "protected_artifact_unavailable"


def _assertion(action: str, purpose: str) -> AuthorizationAssertion | None:
    envelope, principal_id = get_envelope() or {}, get_principal_id()
    tenant_id = envelope.get("tenant_id")
    if not isinstance(principal_id, str) or not isinstance(tenant_id, str):
        return None
    return AuthorizationAssertion(
        principal_id=principal_id, tenant_id=tenant_id,
        action=action, purpose=purpose,
    )


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register the bounded protected-artifact surface."""

    @mcp.tool(name="protected_artifact_create")
    @operational(
        input_model=ProtectedArtifactCreateInput,
        output_model=ProtectedArtifactCreateOutput,
    )
    def create(
        descriptor: dict[str, Any], content: dict[str, Any],
    ) -> ToolResult[ProtectedArtifactCreateOutput]:
        descriptor_model = ProtectedContentDescriptor.model_validate(descriptor)
        assertion = _assertion("create", descriptor_model.purpose)
        if assertion is None:
            return fail(_ERROR)
        try:
            status, artifact = get_runtime().get_protected_artifact_store().create_or_match(
                descriptor_model, content, assertion,
            )
            return ProtectedArtifactCreateOutput(status=status, artifact=artifact)
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="protected_artifact_project")
    @deterministic(
        input_model=ProtectedArtifactRefInput,
        output_model=ProtectedArtifactProjectOutput,
    )
    def project(artifact: dict[str, Any]) -> ToolResult[ProtectedArtifactProjectOutput]:
        artifact_model = ProtectedArtifactRef.model_validate(artifact)
        assertion = _assertion("project", artifact_model.descriptor.purpose)
        if assertion is None:
            return fail(_ERROR)
        try:
            projection = get_runtime().get_protected_artifact_store().project(
                artifact_model, assertion,
            )
            return ProtectedArtifactProjectOutput(projection=projection)
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="protected_artifact_tombstone")
    @operational(
        input_model=ProtectedArtifactRefInput,
        output_model=ProtectedArtifactTombstoneOutput,
    )
    def tombstone(artifact: dict[str, Any]) -> ToolResult[ProtectedArtifactTombstoneOutput]:
        artifact_model = ProtectedArtifactRef.model_validate(artifact)
        assertion = _assertion("tombstone", artifact_model.descriptor.purpose)
        if assertion is None:
            return fail(_ERROR)
        try:
            get_runtime().get_protected_artifact_store().tombstone(
                artifact_model, assertion,
            )
            return ProtectedArtifactTombstoneOutput(tombstoned=True)
        except Exception:
            return fail(_ERROR)

    @mcp.tool(name="protected_artifact_materialize")
    @service_only(callers={"integrations"}, binding="protected_artifact")
    @operational(
        input_model=ProtectedArtifactRefInput,
        output_model=ProtectedArtifactMaterializeOutput,
        idempotent=False,
    )
    def materialize(artifact: dict[str, Any]) -> ToolResult[ProtectedArtifactMaterializeOutput]:
        artifact_model = ProtectedArtifactRef.model_validate(artifact)
        assertion = _assertion("materialize", artifact_model.descriptor.purpose)
        if assertion is None:
            return fail(_ERROR)
        try:
            content = get_runtime().get_protected_artifact_store().materialize(
                artifact_model, assertion,
            )
            return ProtectedArtifactMaterializeOutput(content=content)
        except Exception:
            return fail(_ERROR)
