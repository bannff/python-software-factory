"""Public, transport-neutral credential verification composition."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


class CredentialVerifierPort(Protocol):
    def verify(self, token: str, audience: str | None) -> dict[str, Any] | None: ...


@dataclass(frozen=True, slots=True)
class RuntimeCredentialVerifier:
    runtime: Any

    def verify(self, token: str, audience: str | None) -> dict[str, Any] | None:
        workload = self.runtime.workload_credentials.verify(token, audience)
        if workload is not None:
            claims = workload.model_dump(mode="json")
            return {
                "subject": workload.subject,
                "tenant_id": workload.tenant_id,
                "client_id": workload.credential_id,
                "scopes": workload.scopes,
                "roles": (workload.role,),
                "expires_at": workload.expires_at,
                "claims": claims,
            }
        result = self.runtime.verify_access_token(
            token=token, required_audience=audience,
            required_scopes=None, envelope=None,
        )
        if not result.get("ok") or not isinstance(result.get("principal"), dict):
            return None
        principal = result["principal"]
        claims = result.get("claims") if isinstance(result.get("claims"), dict) else {}
        subject = principal.get("subject")
        if not isinstance(subject, str) or not subject:
            return None
        return {
            "subject": subject,
            "tenant_id": principal.get("tenant_id"),
            "client_id": str(claims.get("client_id") or claims.get("aud") or subject),
            "scopes": tuple(principal.get("scopes") or ()),
            "roles": tuple(principal.get("roles") or claims.get("cognito:groups") or ()),
            "expires_at": claims.get("exp"),
            "claims": claims,
        }


def create_credential_verifier(
    *, local_mode: bool = False, workload_credential_provider: Any | None = None,
) -> CredentialVerifierPort:
    """Build configured verification; local memory tokens require explicit opt-in."""
    from .server import get_runtime

    runtime = get_runtime(
        workload_credential_provider=workload_credential_provider)
    if local_mode:
        _seed_local(runtime)
    return RuntimeCredentialVerifier(runtime)


def _seed_local(runtime: Any) -> None:
    backend = getattr(runtime, "_backend", None)
    if getattr(backend, "kind", None) != "memory":
        raise ValueError("local MCP auth requires the Auth memory backend")
    token = os.environ.get("MCP_LOCAL_AUTH_TOKEN", "")
    if not 16 <= len(token) <= 512:
        raise ValueError("MCP_LOCAL_AUTH_TOKEN must contain 16..512 characters")
    subject = os.environ.get("MCP_LOCAL_AUTH_SUBJECT", "local-operator")
    if not subject or len(subject) > 128:
        raise ValueError("MCP_LOCAL_AUTH_SUBJECT must contain 1..128 characters")
    roles = [item for item in os.environ.get("MCP_LOCAL_AUTH_ROLES", "operator").split(",") if item]
    backend.add_user(subject, subject, tenant_id="local", roles=roles)
    backend.seed_token(
        token, subject, audience=os.environ.get("MCP_AUTH_AUDIENCE"),
        ttl=_local_seed_ttl(),
    )


def _local_seed_ttl() -> int:
    """Row-independent P1 fix (2026-09-17, owner-reported live regression):
    ``seed_token``'s own default ``ttl=3600`` (one hour) was silently
    inherited here, so any local dev session outliving an hour lost ALL
    MCP access with a generic, misleading 401 — a real bug for the norm
    (long-running dogfood/loop work), not the exception. A local
    machine's own dev token has no meaningful reason to expire hourly, so
    default to ``seed_token``'s own maximum allowed value (86400s = 24h,
    see ``MemoryBackend.seed_token``'s ``ttl > 86400`` bound) rather than
    widening that shared validation ceiling for every other caller.
    ``MCP_LOCAL_AUTH_TOKEN_TTL_SECONDS`` lets an owner who genuinely needs
    a shorter-lived local token override it down; ``seed_token`` itself
    still refuses anything outside 1..86400, so this can never silently
    exceed that shared bound."""
    raw = os.environ.get("MCP_LOCAL_AUTH_TOKEN_TTL_SECONDS", "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return 86400


__all__ = ["CredentialVerifierPort", "create_credential_verifier"]
