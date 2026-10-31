from __future__ import annotations

from typing import Any, Protocol

from factory.auth.runtime.envelope import Envelope
from factory.auth.runtime.workload_models import (
    AccessCredential, IssuedWorkloadCredential, WorkloadGrant,
)


class WorkloadGrantPolicyPort(Protocol):
    """Trusted authority that may approve only the exact requested grant."""

    def authorize(self, grant: WorkloadGrant, *, tenant_id: str,
                  audience: str) -> WorkloadGrant | None: ...


class WorkloadCredentialProvider(Protocol):
    """Provider-neutral one-shot workload credential authority."""

    def issue(self, grant: WorkloadGrant, *, workflow_run_id: str,
              attempt_id: str, revision: int,
              ) -> IssuedWorkloadCredential | AccessCredential: ...

    def verify(self, token: str, audience: str | None) -> AccessCredential | None: ...

    def revoke(self, credential_id: str, *, workflow_run_id: str,
               attempt_id: str, revision: int, manifest_digest: str) -> bool: ...


class AuthBackend(Protocol):
    """Protocol defining the interface for authentication backends.
    
    All backends must implement these methods to be pluggable.
    Methods follow Single Responsibility Principle - each does one thing.
    """
    kind: str

    def health_check(self) -> dict[str, Any]:
        """Check backend connectivity and health."""
        ...

    def verify_access_token(
        self,
        token: str,
        *,
        required_audience: str | None,
        required_scopes: list[str] | None,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Verify an access token and extract claims."""
        ...

    def introspect_token(self, token: str, *, envelope: Envelope) -> dict[str, Any]:
        """Introspect a token to check if it's active."""
        ...

    def resolve_principal(self, *, envelope: Envelope) -> dict[str, Any]:
        """Resolve principal from envelope context."""
        ...

    def refresh_token(
        self,
        refresh_token: str,
        *,
        scope: str | None = None,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Exchange a refresh token for a new access token."""
        ...

    def revoke_token(
        self,
        token: str,
        *,
        token_type_hint: str | None = None,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Revoke an access or refresh token."""
        ...

    def get_user_info(
        self,
        access_token: str,
        *,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Get user info from the IdP userinfo endpoint."""
        ...

    def exchange_token(
        self,
        subject_token: str,
        *,
        subject_token_type: str,
        requested_token_type: str | None = None,
        audience: str | None = None,
        scope: str | None = None,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Exchange one token for another (delegation, impersonation)."""
        ...
