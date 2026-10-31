"""Fail-closed protected-content persistence and telemetry projections."""
from __future__ import annotations

from typing import Any

from .protected_content import ProtectedArtifactRef, sanitize_protected_error
from .protected_errors import safe_projection
from .protected_fields import (
    EXCEPTION_FIELDS as _EXCEPTION_KEYS,
    INLINE_SENSITIVE_FIELDS as _INLINE_SENSITIVE,
    SENSITIVE_FIELDS as _SENSITIVE,
    field_name as _field_name,
    plain as _plain,
    sensitive_key as _sensitive_key,
)
from .protected_projection import safe_exception, telemetry_projection

PROTECTED_OPERATION_ERROR_TYPE = "ProtectedOperationError"
PROTECTED_OPERATION_ERROR_MESSAGE = "Protected operation failed"
PROTECTED_OPERATION_ERROR_CODE = "protected-operation-failed"

_PROTECTED_SAFE_FIELDS = frozenset({
    "action", "artifact", "artifacts", "artifact_kind", "artifact_ref",
    "attempt_id", "attempt_revision_argument", "brick_name", "classification",
    "code", "connection_ref", "continuation", "count", "data", "descriptor",
    "digest", "equals", "error", "error_pointer",
    "event_type", "fingerprint", "gateway", "id", "idempotency_key",
    "idempotency_key_argument", "intent_digest", "kind", "lease_seconds",
    "max_attempts", "max_continuations", "message_id", "metadata", "name", "next",
    "ok",
    "output_sha256", "owner_principal_id", "pointer", "profile_version",
    "projection_profile",
    "purpose", "receipt", "receipts", "recipient_count", "ref", "result",
    "retryable",
    "result_projection", "retention_until", "run_id_argument", "schema_version",
    "service_binding", "sha256", "status", "steps", "structured_content", "success",
    "tags",
    "target", "task_mode", "task_options", "task_outcome", "task_payload",
    "task_type", "tenant_id", "tool_name", "tool_target", "transport_envelope_sha256", "type",
    "values", "version",
})


def _artifact_bound(value: Any) -> bool:
    value = _plain(value)
    if isinstance(value, dict):
        keys = {_field_name(key) for key in value}
        try:
            ProtectedArtifactRef.model_validate(value)
            return True
        except Exception:
            pass
        return (
            value.get("protected_content") is True
            or value.get("protected") is True
            or "artifact_ref" in keys
            or "artifact" in keys
            or any(_artifact_bound(item) for item in value.values())
        )
    return any(_artifact_bound(item) for item in value) if isinstance(value, list) else False
def _contains_protected_error(value: Any) -> bool:
    value = _plain(value)
    if isinstance(value, dict):
        normalized = {_field_name(key): item for key, item in value.items()}
        if normalized.get("type") == PROTECTED_OPERATION_ERROR_TYPE:
            return True
        if normalized.get("code") == PROTECTED_OPERATION_ERROR_CODE:
            return True
        return any(_contains_protected_error(item) for item in value.values())
    return any(_contains_protected_error(item) for item in value) if isinstance(value, list) else False
def _reject_inline(
    value: Any, fields: frozenset[str] = _INLINE_SENSITIVE, parent: str = "",
) -> None:
    value = _plain(value)
    if isinstance(value, dict):
        for key, item in value.items():
            field = _field_name(key)
            safe_error_message = (
                field == "message" and parent in _EXCEPTION_KEYS
                and item == "operation failed"
            )
            empty_transport_content = field == "content" and item == []
            redacted_sensitive = (
                isinstance(item, str)
                and item in {"[protected]", "operation failed"}
            )
            if _sensitive_key(key, fields) and not (
                safe_error_message or empty_transport_content or redacted_sensitive
            ):
                raise ValueError("protected inline content is forbidden")
            _reject_inline(item, fields, field)
    elif isinstance(value, list):
        for item in value:
            _reject_inline(item, fields, parent)
def _reject_unapproved_protected(value: Any) -> None:
    value = _plain(value)
    if isinstance(value, dict):
        for key, item in value.items():
            field = _field_name(key)
            if field == "content" and item == []:
                continue
            if field not in _PROTECTED_SAFE_FIELDS:
                raise ValueError("protected inline content is forbidden")
            _reject_unapproved_protected(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unapproved_protected(item)


def validate_protected_persistence(
    value: Any, *, protected: bool | None = None,
) -> Any:
    """Reject inline or unapproved protected content on every durable route."""
    plain = _plain(value)
    strict = protected is None and _artifact_bound(plain)
    if strict:
        _reject_unapproved_protected(plain)
    else:
        _reject_inline(plain, _SENSITIVE if protected else _INLINE_SENSITIVE)
    return plain


def is_protected_payload(value: Any) -> bool:
    """Classify artifact, inline-sensitive, or protected-error payloads."""
    plain = _plain(value)
    try:
        _reject_inline(plain, _SENSITIVE if _artifact_bound(plain) else _INLINE_SENSITIVE)
    except ValueError:
        return True
    return _artifact_bound(plain) or _contains_protected_error(plain)


def _protected_argument_marker(value: Any) -> bool:
    value = _plain(value)
    if not isinstance(value, dict):
        return False
    keys = {_field_name(key) for key in value}
    if value.get("protected") is True or value.get("protected_content") is True:
        return True
    if "artifact_ref" in keys or "artifact" in keys:
        return True
    return bool(keys & _INLINE_SENSITIVE)


def is_protected_operation(tool_name: str | None, arguments: Any = None) -> bool:
    """Identify protected effects by canonical name or direct protected args."""
    normalized = _field_name(tool_name)
    by_name = (
        normalized.endswith("communications_send_email")
        or normalized.endswith("integrations_call")
        or "business_content" in normalized
        or "protected_artifact" in normalized
        or "protected_email" in normalized
        or "workload_credential" in normalized
    )
    return by_name or _protected_argument_marker(arguments)


def _protected_error_envelope() -> dict[str, str]:
    return {
        "type": PROTECTED_OPERATION_ERROR_TYPE,
        "code": PROTECTED_OPERATION_ERROR_CODE,
    }


def _protected_projection(value: Any) -> Any:
    if isinstance(value, dict):
        fields = {_field_name(key) for key in value}
        if {"type", "message"} & fields or "code" in fields:
            return _protected_error_envelope()
        output: dict[str, Any] = {}
        for key, item in value.items():
            field = _field_name(key)
            if _sensitive_key(key):
                continue
            elif field in _EXCEPTION_KEYS:
                output[key] = _protected_error_envelope()
            else:
                output[key] = _protected_projection(item)
        return output
    if isinstance(value, list):
        return [_protected_projection(item) for item in value]
    return value
def protected_error_text(value: Any, *, protected: bool = False) -> str:
    """Return a durable-safe error while keeping retry decisions separate."""
    return PROTECTED_OPERATION_ERROR_CODE if protected else sanitize_protected_error(str(value))


def protected_error_value(value: Any, *, protected: bool = False) -> Any:
    """Project an error/envelope without copying protected exception text."""
    if not protected:
        return safe_projection(_plain(value))
    if isinstance(value, str):
        return _protected_error_envelope()
    return _protected_projection(_plain(value))
