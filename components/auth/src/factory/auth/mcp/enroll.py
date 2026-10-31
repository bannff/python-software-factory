"""OAuth authorization-code enrollment tools (the "connect" flow).

- ``auth.oauth_enroll_begin``: authenticated user starts a connection; returns a
  provider authorize URL + a single-use ``state``. PKCE verifier + owner/tenant
  are captured server-side against that state.
- ``auth.oauth_enroll_complete``: the api callback forwards ``state`` + ``code``;
  identity is re-derived FROM the stored state (the browser redirect carries no
  bearer), the code is exchanged for a refresh token, and the token is enrolled
  into the vault via the broker. Returns only {status, generation} — never a token.

Both are public (@operational). The exchange + slot write happen entirely inside
this tool's call stack; no secret crosses back to the caller.
"""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlencode

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, get_principal_id, ok, operational,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.enroll import (
    OAuthEnrollBeginInput, OAuthEnrollBeginOutput, OAuthEnrollCompleteInput,
    OAuthEnrollCompleteOutput,
)
from ..runtime.egress_models import SlotCoordinate
from ..runtime.enrollment_state import EnrollmentRecord, new_pkce, new_state
from ..runtime.oauth_provider_registry import resolve_oauth_provider


def register(mcp: Any, get_state_store: Callable[[], Any],
             get_exchanger: Callable[[], Any], get_broker: Callable[[], Any]) -> None:
    """Register the connect-flow tools."""

    @typed_tool(mcp, name="auth.oauth_enroll_begin")
    @operational(input_model=OAuthEnrollBeginInput, output_model=OAuthEnrollBeginOutput)
    def oauth_enroll_begin(provider_id: str, connection_ref: str) -> ToolResult[OAuthEnrollBeginOutput]:
        import time
        envelope, owner_id = get_envelope() or {}, get_principal_id()
        tenant_id = envelope.get("tenant_id")
        if not isinstance(owner_id, str) or not owner_id \
                or not isinstance(tenant_id, str) or not tenant_id:
            return fail("unauthenticated_context")
        provider = resolve_oauth_provider(provider_id)
        if provider is None or not provider.configured():
            return fail("oauth_provider_not_configured")
        redirect = provider.default_redirect()
        state = new_state()
        verifier, challenge = new_pkce()
        get_state_store().put(state, EnrollmentRecord(
            provider_id=provider_id, connection_ref=connection_ref,
            owner_id=owner_id, tenant_id=tenant_id, redirect_uri=redirect,
            code_verifier=verifier, created_at=time.time()))
        params = {
            "response_type": "code", "client_id": provider.client_id,
            "redirect_uri": redirect, "scope": " ".join(provider.scopes),
            "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{provider.authorize_url}?{urlencode(params)}"
        return ok(OAuthEnrollBeginOutput(authorize_url=url, state=state))

    @typed_tool(mcp, name="auth.oauth_enroll_complete")
    @operational(input_model=OAuthEnrollCompleteInput,
                 output_model=OAuthEnrollCompleteOutput, idempotent=False)
    def oauth_enroll_complete(state: str, code: str) -> ToolResult[OAuthEnrollCompleteOutput]:
        record = get_state_store().take(state)
        if record is None:
            return fail("invalid_or_expired_state")
        provider = resolve_oauth_provider(record.provider_id)
        if provider is None:
            return fail("oauth_provider_not_configured")
        try:
            secret = get_exchanger().exchange(
                provider, code=code, code_verifier=record.code_verifier,
                redirect_uri=record.redirect_uri)
        except Exception:
            return fail("oauth_exchange_failed")
        coord = SlotCoordinate(
            tenant_id=record.tenant_id, owner_id=record.owner_id,
            provider_id=record.provider_id, connection_ref=record.connection_ref,
            slot_kind=provider.secret_slot_kind)
        try:
            generation = get_broker().enroll(coord, secret)
        except Exception:
            return fail("enrollment_failed")
        if generation is None:
            return fail("already_connected")
        return ok(OAuthEnrollCompleteOutput(status="connected", generation=generation))


__all__ = ["register"]
