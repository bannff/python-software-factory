"""Operational methods for auth runtime."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.auth.runtime.envelope import parse_envelope

if TYPE_CHECKING:
    from factory.auth.runtime.ports import AuthBackend


def verify_access_token(
    backend: "AuthBackend | None",
    *,
    token: str,
    required_audience: str | None,
    required_scopes: list[str] | None,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    return backend.verify_access_token(
        token,
        required_audience=required_audience,
        required_scopes=required_scopes,
        envelope=env,
    )


def introspect_token(
    backend: "AuthBackend | None",
    *,
    token: str,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    out = backend.introspect_token(token, envelope=env)
    return {"ok": True, **out}


def resolve_principal(
    backend: "AuthBackend | None",
    *,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": True, "principal": None, "source": "unknown"}
    return backend.resolve_principal(envelope=env)


def refresh_token(
    backend: "AuthBackend | None",
    *,
    refresh_token: str,
    scope: str | None = None,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    """Exchange refresh token for new access token."""
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    return backend.refresh_token(refresh_token, scope=scope, envelope=env)


def revoke_token(
    backend: "AuthBackend | None",
    *,
    token: str,
    token_type_hint: str | None = None,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    """Revoke an access or refresh token."""
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    return backend.revoke_token(token, token_type_hint=token_type_hint, envelope=env)


def get_user_info(
    backend: "AuthBackend | None",
    *,
    access_token: str,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    """Get user info from IdP userinfo endpoint."""
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    return backend.get_user_info(access_token, envelope=env)


def exchange_token(
    backend: "AuthBackend | None",
    *,
    subject_token: str,
    subject_token_type: str,
    requested_token_type: str | None = None,
    audience: str | None = None,
    scope: str | None = None,
    envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    """Exchange one token for another (RFC 8693)."""
    env = parse_envelope(envelope)
    if backend is None:
        return {"ok": False, "error": "backend_not_configured"}
    return backend.exchange_token(
        subject_token,
        subject_token_type=subject_token_type,
        requested_token_type=requested_token_type,
        audience=audience,
        scope=scope,
        envelope=env,
    )
