"""MCP-only normalization for Auth runtime dictionaries."""
from __future__ import annotations

import re
from typing import Any, TypeVar

from factory.mcp_utils.interface import ToolResult, fail
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_EXPECTED_DOMAIN_ERRORS = frozenset({
    "backend_not_configured", "invalid_token", "invalid_or_expired",
    "token_revoked", "expired", "audience_mismatch", "missing_scopes",
    "user_not_found", "tenant_mismatch", "missing_kid", "unknown_kid",
    "invalid_claims", "issuer_mismatch", "invalid_token_use",
    "invalid_refresh_token", "refresh_failed", "configuration_error",
    "token_refresh_failed", "revocation_failed", "invalid_subject_token",
    "not_supported", "token_exchange_failed", "userinfo_failed",
    "authoring_disabled", "authoring_error", "validation_failed",
})
_PUBLIC_PAYLOAD_HIDDEN_KEYS = frozenset({
    "access_token", "access_tokens", "refresh_token", "refresh_tokens", "id_token",
    "id_tokens", "token", "tokens", "authorization", "credential", "credentials",
    "password", "secret", "secrets", "client_secret", "api_key", "private_key",
    "assertion", "client_assertion", "details", "error", "error_description",
    "error_descriptions", "traceback", "tracebacks", "stack", "stacktrace", "debug",
    "diagnostic", "diagnostics", "exception", "exceptions", "message", "reason",
})


def _normalized_key(key: str) -> str:
    """Normalize common key spellings without matching partial field names."""
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", snake_case.lower()).strip("_")


def sanitize_public_payload(value: Any) -> Any:
    """Recursively remove secret and diagnostic fields from opaque provider data."""
    if isinstance(value, dict):
        return {
            key: sanitize_public_payload(item)
            for key, item in value.items()
            if isinstance(key, str) and _normalized_key(key) not in _PUBLIC_PAYLOAD_HIDDEN_KEYS
        }
    if isinstance(value, list):
        return [sanitize_public_payload(item) for item in value]
    return value


def known_error(raw: dict[str, Any], *, fallback: str | None = None) -> str | None:
    """Return an expected safe error, using an operation fallback for an empty value."""
    error = raw.get("error")
    if error in (None, ""):
        return fallback if raw.get("ok") is False else None
    return error if isinstance(error, str) and error in _EXPECTED_DOMAIN_ERRORS else None


def operation_output(
    raw: dict[str, Any], model: type[T], *, fallback_error: str, **values: Any,
) -> ToolResult[T]:
    """Return typed expected outcomes; hide unclassified adapter details."""
    error = known_error(raw, fallback=fallback_error)
    if raw.get("error") not in (None, "") and error is None:
        return fail("auth_backend_error")
    return model.model_validate({**values, "ok": bool(raw.get("ok", True)), "error": error})


def backend_failure() -> ToolResult[None]:
    """Stable failure envelope for an unclassified backend response."""
    return fail("auth_backend_error")
