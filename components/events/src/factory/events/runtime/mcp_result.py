"""Events-local normalization for typed and legacy MCP result envelopes."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from factory.mcp_utils.interface import ToolResult, is_bounded_json, to_plain_json

_FAILED_STATUSES = frozenset({
    "failed", "failure", "error", "errored", "cancelled", "canceled",
    "aborted", "timeout", "timed_out",
})
_MAX_IDEMPOTENCY_LENGTH = 256
_MEMORY_REQUIRED_FIELDS = frozenset({
    "id", "user_id", "content", "memory_type", "category", "metadata",
    "relevance_score", "created_at",
})
_MEMORY_FIELDS = _MEMORY_REQUIRED_FIELDS | {"updated_at", "expires_at"}


class _SuccessEnvelope(BaseModel):
    """Strict serialized success envelope accepted from an MCP tool."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["v1"]
    ok: Literal[True]
    data: dict[str, JsonValue]
    error: None = None
    idempotency_key: str | None = Field(default=None, max_length=_MAX_IDEMPOTENCY_LENGTH)


def successful_data(
    result: Any, *, reject_data_error: bool = True,
) -> dict[str, Any] | None:
    """Return plain bounded data from typed, serialized-v1, or legacy success.

    ``reject_data_error`` defaults to strict failure-marker handling. A typed
    domain output may intentionally use an inner ``error`` field for a normal
    negative outcome, in which case the consumer opts out explicitly.
    """
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            return None
        candidate = result.data
    elif isinstance(result, Mapping) and "schema_version" in result:
        candidate = _serialized_success_data(result)
        if candidate is None:
            return None
    elif isinstance(result, Mapping):
        candidate = result
    else:
        return None
    candidate = to_plain_json(candidate)
    if not isinstance(candidate, Mapping) or not is_bounded_json(candidate):
        return None
    if "ok" in candidate and candidate["ok"] is not True:
        return None
    if "success" in candidate and candidate["success"] is not True:
        return None
    if reject_data_error and "error" in candidate and candidate["error"] is not None:
        return None
    status = candidate.get("status")
    if isinstance(status, str):
        normalized = re.sub(r"[-\s]+", "_", status.strip().casefold())
        if normalized in _FAILED_STATUSES:
            return None
    return dict(candidate)


def legacy_memory_record(result: Any) -> dict[str, Any] | None:
    """Validate an explicitly supported bare legacy Memory result."""
    if isinstance(result, BaseModel):
        candidate = result.model_dump(mode="json")
    else:
        candidate = to_plain_json(result)
    if not isinstance(candidate, Mapping) or not is_bounded_json(candidate):
        return None
    keys = set(candidate)
    if not _MEMORY_REQUIRED_FIELDS <= keys or not keys <= _MEMORY_FIELDS:
        return None
    if any(
        not isinstance(candidate.get(key), str) or not candidate.get(key)
        for key in ("id", "user_id", "content", "memory_type", "category", "created_at")
    ):
        return None
    if not isinstance(candidate.get("metadata"), Mapping):
        return None
    score = candidate.get("relevance_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    if not 0.0 <= float(score) <= 1.0:
        return None
    if any(
        candidate.get(key) is not None and not isinstance(candidate.get(key), str)
        for key in ("updated_at", "expires_at")
    ):
        return None
    return dict(candidate)


def _serialized_success_data(result: Mapping[str, Any]) -> dict[str, Any] | None:
    """Validate the outer v1 envelope before exposing its data to consumers."""
    candidate = to_plain_json(dict(result))
    if not isinstance(candidate, Mapping) or not is_bounded_json(candidate):
        return None
    try:
        envelope = _SuccessEnvelope.model_validate(candidate)
    except ValidationError:
        return None
    return dict(envelope.data)


__all__ = ["successful_data", "legacy_memory_record"]
