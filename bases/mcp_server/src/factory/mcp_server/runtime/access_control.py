"""Native MCP authentication and policy enforcement adapters."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from factory.mcp_utils.interface import (
    AccessDecision, AccessOperation, AccessPrincipal, reset_envelope, set_envelope,
)

from .workload_access import workload_context


@dataclass(frozen=True, slots=True)
class GatewayAccessController:
    decision_point: Any
    local_principal: AccessPrincipal | None = None

    def principal(self) -> AccessPrincipal | None:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        if token is None or not token.subject:
            # Trusted local stdio/in-process transport carries no HTTP bearer
            # context. On HTTP, unauthenticated requests are already 401'd by the
            # auth middleware upstream of here, so this fallback only fires for
            # stdio — and only when local mode explicitly opted in (else None ⇒
            # deny). Permissions still evaluates this server-owned principal.
            return self.local_principal
        claims = token.claims if isinstance(token.claims, dict) else {}
        return AccessPrincipal(
            subject=token.subject, tenant_id=_tenant(claims),
            client_id=token.client_id, scopes=tuple(token.scopes),
            roles=tuple(_roles(claims)), expires_at=token.expires_at, claims=claims,
        )

    def decide(
        self, principal: AccessPrincipal, operation: AccessOperation,
    ) -> AccessDecision:
        workload_context_data, denial = workload_context(principal, operation)
        if denial is not None:
            return AccessDecision(allowed=False, reason=denial)
        try:
            raw = self.decision_point.decide(
                action=f"mcp:{operation.action}",
                resource={"type": "mcp-tool", "id": operation.public_name},
                context={
                    "brick": operation.brick, "source_name": operation.source_name,
                    "category": operation.category,
                    "is_operator": "operator" in principal.roles,
                    "scopes": list(principal.scopes),
                    "roles": list(principal.roles),
                    **workload_context_data,
                },
                principal_id=principal.subject, tenant_id=principal.tenant_id,
            )
        except Exception:
            return AccessDecision(allowed=False, reason="policy_unavailable")
        allowed = raw.get("decision") == "allow"
        return AccessDecision(
            allowed=allowed, reason=str(raw.get("reason") or "policy_denied"),
            policy_id=raw.get("policy_id"), rule_id=raw.get("rule_id"),
        )

    def envelope(self, principal: AccessPrincipal, tool_name: str):
        return set_envelope({
            "principal_id": principal.subject, "tenant_id": principal.tenant_id,
            "tool_name": tool_name,
            "attributes": {"client_id": principal.client_id},
        })

    @staticmethod
    def reset(token: Any) -> None:
        reset_envelope(token)


class SDKTokenVerifier:
    def __init__(self, verifier: Any, audience: str | None) -> None:
        self._verifier, self._audience = verifier, audience

    async def verify_token(self, token: str) -> Any | None:
        verified = self._verifier.verify(token, self._audience)
        if verified is None:
            return None
        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token, client_id=verified["client_id"],
            scopes=list(verified["scopes"]), expires_at=verified["expires_at"],
            subject=verified["subject"], claims={
                **verified["claims"], "tenant_id": verified["tenant_id"],
                "roles": list(verified["roles"]),
            },
        )


def build_access_components() -> tuple[GatewayAccessController, SDKTokenVerifier]:
    local = os.environ.get("MCP_LOCAL_AUTH", "").lower() in {"1", "true", "yes"}
    from factory.auth.interface import create_credential_verifier
    from factory.permissions.interface import create_decision_point

    controller = GatewayAccessController(
        create_decision_point(local_mode=local),
        local_principal=_local_principal() if local else None,
    )
    verifier = SDKTokenVerifier(
        create_credential_verifier(local_mode=local),
        os.environ.get("MCP_AUTH_AUDIENCE"),
    )
    return controller, verifier


def _local_principal() -> AccessPrincipal:
    """Server-owned principal for trusted local stdio/in-process transports.

    Operator role so local dev reaches authoring tools; the local policy still
    governs it via the decision point. Never derived from caller-supplied input.
    """
    return AccessPrincipal(
        subject="svc:local", tenant_id=os.environ.get("MCP_LOCAL_TENANT") or None,
        client_id="local-stdio", scopes=(), roles=("operator",),
        expires_at=None, claims={},
    )


def auth_settings() -> Any:
    from mcp.server.auth.settings import AuthSettings

    local = os.environ.get("MCP_LOCAL_AUTH", "").lower() in {"1", "true", "yes"}
    issuer = os.environ.get("MCP_AUTH_ISSUER_URL") or ("http://127.0.0.1:8000" if local else None)
    resource = os.environ.get("MCP_RESOURCE_SERVER_URL") or ("http://127.0.0.1:8000/mcp" if local else None)
    if not issuer or not resource:
        raise ValueError("MCP_AUTH_ISSUER_URL and MCP_RESOURCE_SERVER_URL are required")
    scopes = [
        item.strip() for item in os.environ.get("MCP_AUTH_REQUIRED_SCOPES", "").split(",")
        if item.strip()
    ]
    return AuthSettings(
        issuer_url=issuer, resource_server_url=resource,
        required_scopes=scopes or None,
    )


def _roles(claims: dict[str, Any]) -> list[str]:
    value = claims.get("roles") or claims.get("cognito:groups") or []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _tenant(claims: dict[str, Any]) -> str | None:
    value = claims.get("tenant_id")
    return value if isinstance(value, str) and value else None


__all__ = ["GatewayAccessController", "auth_settings", "build_access_components"]
