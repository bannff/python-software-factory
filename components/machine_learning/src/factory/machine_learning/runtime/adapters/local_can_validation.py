"""Lookup-key and payload validation for local CAN lifecycle authority."""
from __future__ import annotations

from typing import Any

from ..can_lifecycle_canonical import canonical_json
from ..can_lifecycle_contracts import CanLifecycleAttempt


def _decode(model, content: bytes):
    value = model.model_validate_json(content)
    if canonical_json(value.model_dump(mode="json")) != content:
        raise ValueError("lifecycle authority record is not canonical")
    return value


def decode_attempt(content: bytes, operation: str, attempt_id: str):
    value = _decode(CanLifecycleAttempt, content)
    if value.operation != operation or value.attempt_id != attempt_id:
        raise ValueError("lifecycle attempt lookup key mismatch")
    return value


def decode_effect(model, content: bytes, effect_id: str):
    value = _decode(model, content)
    if value.effect_id != effect_id:
        raise ValueError("lifecycle effect lookup key mismatch")
    return value


def validate_terminal(value: Any, record: CanLifecycleAttempt) -> dict:
    expected_status = "completed" if record.state == "succeeded" else "failed"
    if not isinstance(value, dict) or (
        value.get("operation") != record.operation
        or value.get("attempt_id") != record.attempt_id
        or value.get("request_sha256") != record.request_sha256
        or value.get("status") != expected_status
    ):
        raise ValueError("lifecycle terminal identity mismatch")
    return value


__all__ = ["decode_attempt", "decode_effect", "validate_terminal"]
