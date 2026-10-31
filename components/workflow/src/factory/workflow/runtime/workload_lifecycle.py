"""Domain-neutral host-side workload credential lifecycle coordination."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from factory.auth.interface import WorkloadGrant
from factory.mcp_utils.interface import get_envelope

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ISSUE = {"brick_name": "auth", "tool_name": "auth.issue_workload_credential"}
_REVOKE = {"brick_name": "auth", "tool_name": "auth.revoke_workload_credential"}


@dataclass(frozen=True, slots=True)
class WorkloadLaunchManifest:
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str
    grant: WorkloadGrant
    authority_tenant_id: str

    def __post_init__(self) -> None:
        if not self.workflow_run_id or not self.attempt_id:
            raise ValueError("workload launch requires exact attempt identity")
        if self.revision < 0 or _SHA256.fullmatch(self.manifest_digest) is None:
            raise ValueError("workload launch binding is malformed")
        grant = self.validated_grant()
        if not self.authority_tenant_id \
                or self.authority_tenant_id != grant.tenant_id:
            raise ValueError("workload launch tenant authority mismatch")

    def validated_grant(self) -> WorkloadGrant:
        """Revalidate canonical hashes, including after accidental list mutation."""
        if not isinstance(self.grant, WorkloadGrant):
            raise TypeError("workload launch requires a frozen WorkloadGrant")
        grant = WorkloadGrant.model_validate(self.grant.model_dump())
        if grant.manifest_digest != self.manifest_digest:
            raise ValueError("workload grant must match launch manifest digest")
        return grant

    @property
    def attempt_binding(self) -> dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "attempt_id": self.attempt_id, "revision": self.revision,
            "manifest_digest": self.manifest_digest,
        }


@dataclass(frozen=True, slots=True)
class WorkloadLease:
    manifest: WorkloadLaunchManifest
    credential_id: str
    endpoint: str


class WorkloadActivatorPort(Protocol):
    async def activate(self, manifest: WorkloadLaunchManifest,
                       access_token: str) -> str:
        """Create the host proxy endpoint; never inject bearer into workload."""
        ...

    async def deactivate(self, endpoint: str) -> None: ...


class WorkloadAttemptRecoveryError(RuntimeError):
    """Recovered prior authority was revoked; caller must use a new attempt."""


class WorkloadLifecycleCoordinator:
    """Issue → host activate → revoke with no durable bearer state."""

    def __init__(self, caller_bound_invoker: Any,
                 activator: WorkloadActivatorPort) -> None:
        self._invoke = caller_bound_invoker
        self._activator = activator

    async def launch(self, manifest: WorkloadLaunchManifest) -> WorkloadLease:
        grant = manifest.validated_grant()
        ambient_tenant = (get_envelope() or {}).get("tenant_id")
        if ambient_tenant != manifest.authority_tenant_id:
            raise ValueError("trusted workload tenant authority is required")
        binding = manifest.attempt_binding
        result = self._invoke(
            _ISSUE, arguments={**binding, "grant": grant.model_dump(mode="json")},
            idempotency_key=(f"workload-issue:{manifest.workflow_run_id}:"
                             f"{manifest.attempt_id}:{manifest.revision}"),
            envelope={"run_id": manifest.workflow_run_id,
                      "tenant_id": manifest.authority_tenant_id}, attempt=binding,
        )
        data = _tool_data(result, "workload credential issue failed")
        if data.get("duplicate") is True:
            recovered = data.get("recovered_credential")
            credential_id = recovered.get("credential_id") \
                if isinstance(recovered, Mapping) else None
            if not isinstance(credential_id, str) or not credential_id:
                raise WorkloadAttemptRecoveryError(
                    "workload duplicate recovery lacked credential identity")
            self._revoke(manifest, credential_id)
            raise WorkloadAttemptRecoveryError(
                "workload credential recovered and revoked; use a new attempt")
        private = _issued_private(data)
        credential = private["credential"]
        credential_id = credential["credential_id"]
        access_token = private["access_token"]
        try:
            endpoint = await self._activator.activate(manifest, access_token)
        except Exception:
            self._revoke(manifest, credential_id)
            raise
        finally:
            access_token = None
        return WorkloadLease(manifest, credential_id, endpoint)

    async def close(self, lease: WorkloadLease) -> None:
        """Remove upstream authority before tearing down the local proxy."""
        try:
            self._revoke(lease.manifest, lease.credential_id)
        finally:
            await self._activator.deactivate(lease.endpoint)

    def _revoke(self, manifest: WorkloadLaunchManifest,
                credential_id: str) -> None:
        binding = manifest.attempt_binding
        result = self._invoke(
            _REVOKE, arguments={**binding, "credential_id": credential_id},
            idempotency_key=f"workload-revoke:{credential_id}",
            envelope={"run_id": manifest.workflow_run_id,
                      "tenant_id": manifest.authority_tenant_id}, attempt=binding,
        )
        data = _tool_data(result, "workload credential revoke failed")
        if data.get("revoked") is not True:
            raise RuntimeError("workload credential revoke failed")


def _tool_data(result: Any, error: str) -> Mapping[str, Any]:
    """Parse NativeEnvelopeInvoker → native tool → ToolResult exactly."""
    if not isinstance(result, Mapping) or result.get("ok") is not True:
        raise RuntimeError(error)
    native = result.get("result")
    structured = native.get("structured_content") if isinstance(native, Mapping) else None
    if not isinstance(structured, Mapping) or structured.get("ok") is not True:
        raise RuntimeError(error)
    data = structured.get("data")
    if not isinstance(data, Mapping):
        raise RuntimeError(error)
    return data


def _issued_private(data: Mapping[str, Any]) -> dict[str, Any]:
    private = data.get("credential")
    if not data.get("issued") or not isinstance(private, Mapping):
        raise RuntimeError("workload credential issue was not unique")
    token = private.get("access_token")
    credential = private.get("credential")
    if not isinstance(token, str):
        raise RuntimeError("workload credential issue returned no secret")
    if not isinstance(credential, Mapping) or not credential.get("credential_id"):
        raise RuntimeError("workload credential issue returned no identity")
    return dict(private)


__all__ = [
    "WorkloadActivatorPort", "WorkloadAttemptRecoveryError",
    "WorkloadLaunchManifest", "WorkloadLease", "WorkloadLifecycleCoordinator",
]
