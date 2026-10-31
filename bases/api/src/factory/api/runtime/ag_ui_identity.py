"""Verified AG-UI bearer identity extraction."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def extract_identity(
    request: Any,
    fallback: Callable[[str, dict[str, Any]], Awaitable[Any]],
) -> dict[str, str] | None:
    """Resolve one bearer through the gateway verifier or legacy Auth tool."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ")
    from factory.mcp_utils.interface import get_service

    verifier = get_service("mcp_token_verifier")
    if verifier is not None and callable(getattr(verifier, "verify_token", None)):
        verified = await verifier.verify_token(token)
        if verified is None:
            return None
        claims = verified.claims if isinstance(verified.claims, dict) else {}
        return _identity(verified.subject, claims.get("tenant_id"))
    result = await fallback("auth_verify_access_token", {"token": token})
    if not isinstance(result, dict) or result.get("ok") is not True:
        return None
    data = result.get("data")
    if not isinstance(data, dict) or data.get("ok") is not True:
        return None
    principal = data.get("principal")
    if not isinstance(principal, dict):
        return None
    return _identity(principal.get("subject"), principal.get("tenant_id"))


def _identity(principal_id: Any, tenant_id: Any) -> dict[str, str] | None:
    if not isinstance(principal_id, str) or not principal_id.strip():
        return None
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return None
    return {"principal_id": principal_id, "tenant_id": tenant_id}


__all__ = ["extract_identity"]
