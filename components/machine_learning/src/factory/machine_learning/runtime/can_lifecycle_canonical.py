"""Canonical and versioned identities for retry-safe ML CAN lifecycle work."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .can_lifecycle_identity import (
    CONFORM_OPERATION, ISSUE_OPERATION, PROJECT_OPERATION, PROMOTE_OPERATION,
    TRAIN_OPERATION,
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _versioned(value: str, kind: str) -> None:
    if "@v1" not in value:
        raise ValueError(f"{kind} semantic identity must contain @v1")


def semantic_request(
    operation: str, request: dict[str, Any], tool_identities: dict[str, str],
) -> tuple[dict[str, Any], str]:
    _versioned(operation, "operation")
    for value in tool_identities.values():
        _versioned(value, "tool")
    payload = dict(request)
    payload.pop("attempt_id", None)
    semantic = {
        "operation": operation, "request": payload,
        "tool_identities": dict(sorted(tool_identities.items())),
    }
    return semantic, hashlib.sha256(canonical_json(semantic)).hexdigest()


def effect_identity(operation: str, request_sha256: str, unit: str) -> str:
    _versioned(operation, "operation")
    _versioned(unit, "effect unit")
    return hashlib.sha256(canonical_json({
        "operation": operation, "request_sha256": request_sha256, "unit": unit,
    })).hexdigest()


__all__ = [
    "CONFORM_OPERATION", "ISSUE_OPERATION", "PROJECT_OPERATION",
    "PROMOTE_OPERATION", "TRAIN_OPERATION", "canonical_json",
    "effect_identity", "semantic_request",
]
