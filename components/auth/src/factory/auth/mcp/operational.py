"""Typed operational MCP tools for Auth."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.models import (
    ExchangeTokenInput, IntrospectTokenOutput, RefreshTokenInput, ResolvePrincipalInput,
    ResolvePrincipalOutput, RevokeTokenInput, TokenInput, TokenOperationOutput,
    UserInfoInput, UserInfoOutput, VerifyAccessTokenInput, VerifyAccessTokenOutput,
)
from .normalization import operation_output, sanitize_public_payload

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime") -> None:
    """Register operational tools with strict public contracts."""

    @mcp.tool(name="auth.verify_access_token")
    @operational(input_model=VerifyAccessTokenInput, output_model=VerifyAccessTokenOutput)
    def verify_access_token(token: str, required_audience: str | None = None,
                            required_scopes: list[str] | None = None, envelope: dict | None = None) -> ToolResult[VerifyAccessTokenOutput]:
        raw = runtime.verify_access_token(token=token, required_audience=required_audience, required_scopes=required_scopes, envelope=envelope)
        return operation_output(raw, VerifyAccessTokenOutput, fallback_error="invalid_token", principal=raw.get("principal"), claims=sanitize_public_payload(raw.get("claims")), missing=raw.get("missing"))

    @mcp.tool(name="auth.introspect_token")
    @operational(input_model=TokenInput, output_model=IntrospectTokenOutput)
    def introspect_token(token: str, envelope: dict | None = None) -> ToolResult[IntrospectTokenOutput]:
        raw = runtime.introspect_token(token=token, envelope=envelope)
        return operation_output(raw, IntrospectTokenOutput, fallback_error="invalid_or_expired", active=bool(raw.get("active")), exp=raw.get("exp"), sub=raw.get("sub"), tenant_id=raw.get("tenant_id"))

    @mcp.tool(name="auth.resolve_principal")
    @operational(input_model=ResolvePrincipalInput, output_model=ResolvePrincipalOutput)
    def resolve_principal(envelope: dict | None = None) -> ToolResult[ResolvePrincipalOutput]:
        raw = runtime.resolve_principal(envelope=envelope)
        return operation_output(raw, ResolvePrincipalOutput, fallback_error="backend_not_configured", principal=raw.get("principal"), source=str(raw.get("source", "unknown")))

    @mcp.tool(name="auth.refresh_token")
    @operational(input_model=RefreshTokenInput, output_model=TokenOperationOutput)
    def refresh_token(refresh_token: str, scope: str | None = None, envelope: dict | None = None) -> ToolResult[TokenOperationOutput]:
        raw = runtime.refresh_token(refresh_token=refresh_token, scope=scope, envelope=envelope)
        return _token_output(raw, fallback_error="token_refresh_failed")

    @mcp.tool(name="auth.revoke_token")
    @operational(input_model=RevokeTokenInput, output_model=TokenOperationOutput)
    def revoke_token(token: str, token_type_hint: str | None = None, envelope: dict | None = None) -> ToolResult[TokenOperationOutput]:
        raw = runtime.revoke_token(token=token, token_type_hint=token_type_hint, envelope=envelope)
        return _token_output(raw, fallback_error="revocation_failed")

    @mcp.tool(name="auth.get_user_info")
    @operational(input_model=UserInfoInput, output_model=UserInfoOutput)
    def get_user_info(access_token: str, envelope: dict | None = None) -> ToolResult[UserInfoOutput]:
        raw = runtime.get_user_info(access_token=access_token, envelope=envelope)
        return operation_output(raw, UserInfoOutput, fallback_error="userinfo_failed", user_info=sanitize_public_payload(raw.get("user_info")))

    @mcp.tool(name="auth.exchange_token")
    @operational(input_model=ExchangeTokenInput, output_model=TokenOperationOutput)
    def exchange_token(subject_token: str, subject_token_type: str, requested_token_type: str | None = None,
                       audience: str | None = None, scope: str | None = None, envelope: dict | None = None) -> ToolResult[TokenOperationOutput]:
        raw = runtime.exchange_token(subject_token=subject_token, subject_token_type=subject_token_type, requested_token_type=requested_token_type, audience=audience, scope=scope, envelope=envelope)
        return _token_output(raw, fallback_error="token_exchange_failed")


def _token_output(raw: dict, *, fallback_error: str) -> ToolResult[TokenOperationOutput]:
    return operation_output(raw, TokenOperationOutput, fallback_error=fallback_error, issued="access_token" in raw,
                            revoked=raw.get("revoked"), token_type=raw.get("token_type"),
                            expires_in=raw.get("expires_in"), scope=raw.get("scope"),
                            issued_token_type=raw.get("issued_token_type"))
