"""Private service-only workload credential lifecycle tools."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, get_service, ok, operational, service_only,
)

from .contracts.workload import (
    IssueWorkloadCredentialInput, IssueWorkloadCredentialOutput,
    PrivateIssuedCredential, RevokeWorkloadCredentialInput,
    RevokeWorkloadCredentialOutput,
)
from ..runtime.workload_credentials import WorkloadCredentialConflict
from ..runtime.workload_models import AccessCredential, WorkloadGrant

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime") -> None:
    """Register hidden tools reachable only through caller-bound invocation."""

    @mcp.tool(name="auth.issue_workload_credential")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=IssueWorkloadCredentialInput,
                 output_model=IssueWorkloadCredentialOutput, idempotent=False)
    def issue_workload_credential(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, grant: WorkloadGrant,
    ) -> ToolResult[IssueWorkloadCredentialOutput]:
        try:
            grant = WorkloadGrant.model_validate(grant)
        except (TypeError, ValueError):
            return fail("workload_grant_denied")
        authorized = _authorize(grant)
        if authorized is None:
            return fail("workload_grant_denied")
        try:
            issued = runtime.issue_workload_credential(
                authorized, workflow_run_id=workflow_run_id,
                attempt_id=attempt_id, revision=revision,
            )
        except WorkloadCredentialConflict:
            return fail("workload_attempt_manifest_conflict")
        if isinstance(issued, AccessCredential):
            return ok(IssueWorkloadCredentialOutput(
                issued=False, duplicate=True, recovered_credential=issued))
        private = PrivateIssuedCredential(
            credential=issued.credential, access_token=issued.access_token)
        return ok(IssueWorkloadCredentialOutput(
            issued=True, duplicate=False, credential=private))

    @mcp.tool(name="auth.revoke_workload_credential")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=RevokeWorkloadCredentialInput,
                 output_model=RevokeWorkloadCredentialOutput)
    def revoke_workload_credential(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, credential_id: str,
    ) -> ToolResult[RevokeWorkloadCredentialOutput]:
        return ok(RevokeWorkloadCredentialOutput(
            revoked=runtime.revoke_workload_credential(
                credential_id, workflow_run_id=workflow_run_id,
                attempt_id=attempt_id, revision=revision,
                manifest_digest=manifest_digest,
            )))


def _authorize(grant: WorkloadGrant) -> WorkloadGrant | None:
    """Resolve trusted gateway authority at invocation and fail closed."""
    audience = os.environ.get("MCP_AUTH_AUDIENCE")
    envelope = get_envelope() or {}
    tenant_id = envelope.get("tenant_id")
    policy = get_service("workload_grant_policy")
    if not audience or not isinstance(tenant_id, str) or not tenant_id:
        return None
    if grant.audience != audience or grant.tenant_id != tenant_id:
        return None
    authorize = getattr(policy, "authorize", None)
    if not callable(authorize):
        return None
    try:
        approved = authorize(grant, tenant_id=tenant_id, audience=audience)
        if not isinstance(approved, WorkloadGrant):
            return None
        if approved.model_dump(mode="json") != grant.model_dump(mode="json"):
            return None
        return WorkloadGrant.model_validate(approved.model_dump(mode="json"))
    except Exception:  # policy failures are safe denials
        return None


__all__ = ["register"]
