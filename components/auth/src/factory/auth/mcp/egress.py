"""Hidden service-only tokenless credentialed-egress tool (caller=integrations).

Registered directly in server.py (excluded from mcp/__init__). Validates the
request against the immutable provider/route registry, rejects any payload
field the route does not allow, resolves the tenant/owner from the trusted
envelope (never the payload), and delegates to the broker. Returns only a
sanitized business result — never a token, secret, or provider header.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, get_principal_id, ok, operational,
    service_only,
)

from .contracts.egress import CredentialedEgressInput, CredentialedEgressOutput
from ..runtime.egress_models import EgressRequest, SlotCoordinate, request_digest
from ..runtime.egress_registry import resolve_route

_ERROR = "credential_egress_denied"


def register(mcp: Any, get_broker: Callable[[], Any]) -> None:
    """Register the hidden integrations-only egress surface."""

    @mcp.tool(name="auth.credentialed_egress")
    @service_only(callers={"integrations"}, binding="credential_egress")
    @operational(input_model=CredentialedEgressInput,
                 output_model=CredentialedEgressOutput, idempotent=False)
    def credentialed_egress(request: dict[str, Any]) -> ToolResult[CredentialedEgressOutput]:
        try:
            req = EgressRequest.model_validate(request)
        except Exception:
            return fail(_ERROR)
        expected = request_digest(
            req.provider_id, req.route_id, req.connection_ref, req.payload)
        if expected != req.request_digest:
            return fail(_ERROR)
        route = resolve_route(req.provider_id, req.route_id)
        if route is None or not route.validate_payload(req.payload):
            return fail(_ERROR)
        coord = _coordinate(req, route.secret_slot_kind)
        if coord is None:
            return fail(_ERROR)
        try:
            result = get_broker().egress(coord, route, req.payload)
        except Exception:
            return fail(_ERROR)
        status = getattr(result, "status", None)
        if status not in ("ok", "unauthorized", "denied"):
            return fail(_ERROR)
        return ok(CredentialedEgressOutput(
            status=status, result=dict(getattr(result, "result", {}) or {})))


def _coordinate(req: EgressRequest, slot_kind: str) -> SlotCoordinate | None:
    envelope = get_envelope() or {}
    tenant_id, owner_id = envelope.get("tenant_id"), get_principal_id()
    if not isinstance(tenant_id, str) or not tenant_id \
            or not isinstance(owner_id, str) or not owner_id:
        return None
    try:
        return SlotCoordinate(
            tenant_id=tenant_id, owner_id=owner_id, provider_id=req.provider_id,
            connection_ref=req.connection_ref, slot_kind=slot_kind)
    except (TypeError, ValueError):
        return None


__all__ = ["register"]
