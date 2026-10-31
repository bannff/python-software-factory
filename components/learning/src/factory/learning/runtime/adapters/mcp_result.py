"""Normalize successful cross-brick MCP results at adapter boundaries."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from factory.mcp_utils.interface import is_bounded_json, to_plain_json
_MAX_IDEMPOTENCY_LENGTH = 256
_LEARNING_EVIDENCE_SEQUENCE_LIMIT = 256
_FAILED_STATUSES = frozenset({
    "failed", "failure", "error", "errored", "cancelled", "canceled",
    "aborted", "timeout", "timed_out",
})


class _SuccessEnvelope(BaseModel):
    """Strict serialized success envelope accepted from an MCP tool."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["v1"]
    ok: Literal[True]
    data: dict[str, JsonValue]
    error: None = None
    idempotency_key: str | None = Field(default=None, max_length=_MAX_IDEMPOTENCY_LENGTH)


def successful_data(
    result: Any,
    *,
    allow_legacy: bool = False,
    validator: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    """Return validated success data from typed, serialized, or legacy MCP data.

    Bare mappings are legacy transport and require both explicit opt-in and a
    shape validator. This keeps each adapter's compatibility decision local
    instead of treating arbitrary data as a successful cross-brick result.
    """
    if allow_legacy and validator is None:
        return None
    data = _unwrap_success(result, allow_legacy=allow_legacy)
    if data is None:
        return None
    if validator is not None:
        try:
            data = validator(data)
        except (TypeError, ValueError, ValidationError):
            return None
        if data is None:
            return None
    return data


def _unwrap_success(result: Any, *, allow_legacy: bool) -> dict[str, Any] | None:
    if result is None:
        return None
    if hasattr(result, "ok"):
        if getattr(result, "schema_version", None) != "v1":
            return None
        if getattr(result, "ok") is not True or not hasattr(result, "model_dump"):
            return None
        try:
            return _validate_envelope(
                to_plain_json(result.model_dump(mode="python"))
            )
        except (TypeError, ValueError):
            return None
    if isinstance(result, Mapping) and "schema_version" in result:
        return _validate_envelope(dict(result))
    if not isinstance(result, Mapping) or not allow_legacy:
        return None
    data = dict(result)
    return data if is_bounded_json(
        data, max_sequence_items=_LEARNING_EVIDENCE_SEQUENCE_LIMIT,
    ) else None


def _validate_envelope(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, Mapping):
        return None
    candidate = dict(candidate)
    if not is_bounded_json(
        candidate, max_sequence_items=_LEARNING_EVIDENCE_SEQUENCE_LIMIT,
    ):
        return None
    try:
        return dict(_SuccessEnvelope.model_validate(candidate).data)
    except ValidationError:
        return None


def validate_games_result(data: dict[str, Any]) -> dict[str, Any] | None:
    """Validate the legacy fields consumed by the GT-findings adapter."""
    scoring = data.get("scoring")
    gt_count = data.get("gt_entries_count")
    blockchain = data.get("blockchain", {})
    if (
        not is_bounded_json(
            data, max_sequence_items=_LEARNING_EVIDENCE_SEQUENCE_LIMIT,
        )
        or not _legacy_success_envelope(data)
        or not isinstance(scoring, Mapping)
    ):
        return None
    if not _legacy_success_envelope(scoring) or not _nonnegative_int(gt_count):
        return None
    if blockchain is not None and (
        not isinstance(blockchain, Mapping)
        or not _legacy_success_envelope(blockchain)
    ):
        return None
    if _bounded_score(scoring.get("f1")) is None:
        return None
    for key in ("precision", "recall"):
        if key in scoring and _bounded_score(scoring[key]) is None:
            return None
    return data


def validate_evals_result(data: dict[str, Any]) -> dict[str, Any] | None:
    """Validate bounded Evals data with no nested scoring errors."""
    if (
        not is_bounded_json(
            data, max_sequence_items=_LEARNING_EVIDENCE_SEQUENCE_LIMIT,
        )
        or not _legacy_success_envelope(data)
        or _contains_evals_error(data)
    ):
        return None
    for container in (data, data.get("aggregate"), data.get("summary")):
        if not isinstance(container, Mapping):
            continue
        for key in ("avg_score", "average_score", "score", "pass_rate"):
            if key in container and _bounded_score(container[key]) is not None:
                return data
    return None


def _legacy_success_envelope(value: Mapping[str, Any]) -> bool:
    """Reject explicit failure markers before domain-specific validation."""
    if "ok" in value and value["ok"] is not True:
        return False
    if "success" in value and value["success"] is not True:
        return False
    if "error" in value and value["error"] is not None:
        return False
    status = value.get("status")
    if isinstance(status, str):
        normalized = re.sub(r"[-\s]+", "_", status.strip().casefold())
        if normalized in _FAILED_STATUSES:
            return False
    return True


def _contains_evals_error(value: Any) -> bool:
    if isinstance(value, Mapping):
        if not _legacy_success_envelope(value):
            return True
        if "error_count" in value:
            count = value["error_count"]
            if not isinstance(count, int) or isinstance(count, bool) or count != 0:
                return True
        if value.get("label") == "error":
            return True
        return any(_contains_evals_error(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_evals_error(item) for item in value)
    return False


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _bounded_score(value: Any) -> float | None:
    if not _finite_number(value):
        return None
    score = float(value)
    return score if 0.0 <= score <= 1.0 else None


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = [
    "successful_data",
    "validate_evals_result",
    "validate_games_result",
]
