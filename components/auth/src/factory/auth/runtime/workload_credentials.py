"""Process-local opaque workload credential provider."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from .workload_models import AccessCredential, IssuedWorkloadCredential, WorkloadGrant


class WorkloadCredentialConflict(ValueError):
    """One durable attempt was reused with a different frozen manifest."""


@dataclass(slots=True)
class _Record:
    credential: AccessCredential
    token_hash: bytes
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str
    revoked: bool = False


class DisabledWorkloadCredentialProvider:
    """Fail-closed authority until local single-process mode is explicit."""

    def issue(self, *_args, **_kwargs):
        raise RuntimeError("workload credential provider is not configured")

    def verify(self, _token: str, _audience: str | None):
        return None

    def revoke(self, _credential_id: str, **_binding) -> bool:
        return False


class LocalOpaqueWorkloadCredentialProvider:
    """Mint random bearer secrets while retaining only SHA-256 hashes.

    State is intentionally process-local: restart invalidates every credential.
    """

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._records: dict[str, _Record] = {}
        self._tokens: dict[bytes, str] = {}
        self._attempts: dict[tuple[str, str, int], tuple[str, str]] = {}
        self._lock = Lock()

    def issue(self, grant: WorkloadGrant, *, workflow_run_id: str,
              attempt_id: str, revision: int,
              ) -> IssuedWorkloadCredential | AccessCredential:
        key = (workflow_run_id, attempt_id, revision)
        now = int(self._clock())
        with self._lock:
            prior = self._attempts.get(key)
            if prior is not None:
                if prior[0] != grant.manifest_digest:
                    raise WorkloadCredentialConflict(
                        "workload attempt is already bound to another manifest")
                return self._records[prior[1]].credential
            token = secrets.token_urlsafe(32)
            credential_id = secrets.token_urlsafe(24)
            credential = AccessCredential(
                credential_id=credential_id, subject=f"svc:squad:{grant.launch_id}",
                tenant_id=grant.tenant_id, audience=grant.audience,
                scopes=tuple(grant.allowed_tools), allowed_tools=tuple(grant.allowed_tools),
                policy_id=grant.policy_id,
                capability_scope_digest=grant.capability_scope_digest,
                manifest_digest=grant.manifest_digest, launch_id=grant.launch_id,
                generation=grant.generation, issued_at=now, expires_at=now + 300,
            )
            digest = _token_hash(token)
            self._records[credential_id] = _Record(
                credential, digest, workflow_run_id, attempt_id, revision,
                grant.manifest_digest,
            )
            self._tokens[digest] = credential_id
            self._attempts[key] = (grant.manifest_digest, credential_id)
            return IssuedWorkloadCredential(
                credential=credential, access_token=token)

    def verify(self, token: str, audience: str | None) -> AccessCredential | None:
        if not isinstance(token, str) or not token:
            return None
        digest = _token_hash(token)
        with self._lock:
            credential_id = self._tokens.get(digest)
            record = self._records.get(credential_id or "")
            if record is None or record.revoked or record.token_hash != digest:
                return None
            credential = record.credential
            if int(self._clock()) >= credential.expires_at:
                return None
            if audience is not None and audience != credential.audience:
                return None
            try:
                AccessCredential.model_validate(credential.model_dump())
            except ValueError:
                return None
            return credential

    def revoke(self, credential_id: str, *, workflow_run_id: str,
               attempt_id: str, revision: int, manifest_digest: str) -> bool:
        """Revoke only the credential bound to this exact attempt and manifest."""
        key = (workflow_run_id, attempt_id, revision)
        with self._lock:
            if self._attempts.get(key) != (manifest_digest, credential_id):
                return False
            record = self._records.get(credential_id)
            if record is None or (
                record.workflow_run_id, record.attempt_id, record.revision,
                record.manifest_digest,
            ) != (workflow_run_id, attempt_id, revision, manifest_digest):
                return False
            if not record.revoked:
                record.revoked = True
                self._tokens.pop(record.token_hash, None)
            return True


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


__all__ = [
    "DisabledWorkloadCredentialProvider", "LocalOpaqueWorkloadCredentialProvider",
    "WorkloadCredentialConflict",
]
