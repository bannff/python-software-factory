"""Credential-safe recursive telemetry projections."""
from __future__ import annotations

import re
from typing import Any

from .protected_content import ProtectedArtifactRef
from .protected_fields import EXCEPTION_FIELDS, field_name, plain, sensitive_key

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COUNT = re.compile(r"(?:^|_)(?:count|total|size|length|items|results|entries|events)$")
_SAFE_ROUTING = frozenset({
    "backend", "brick", "brick_name", "kind", "operation", "operation_name",
    "phase", "provider", "route", "route_name", "status", "tool", "tool_name",
})


def _artifact_bound(value: Any) -> bool:
    value = plain(value)
    if isinstance(value, dict):
        keys = {field_name(key) for key in value}
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


def _count(value: Any) -> int | None:
    if isinstance(value, (dict, list, tuple)):
        return len(value)
    return value if type(value) is int and value >= 0 else None


def telemetry_projection(value: Any, *, protected: bool | None = None) -> dict[str, Any]:
    """Suppress protected aliases while retaining routing, counts, and digests."""
    value = plain(value)
    protected = _artifact_bound(value) if protected is None else protected
    if not isinstance(value, dict):
        return {"value_type": type(value).__name__}
    output: dict[str, Any] = {}
    for key, item in value.items():
        field = field_name(key)
        if sensitive_key(key) or field in EXCEPTION_FIELDS:
            continue
        if field == "artifact_ref" and isinstance(item, str):
            output[key] = item
        elif (field in {"fingerprint", "sha256"} or field.endswith("_digest")) \
                and isinstance(item, str) and _DIGEST.fullmatch(item):
            output[key] = item
        elif _COUNT.search(field):
            count = _count(item)
            if count is not None:
                output[key] = count
        elif isinstance(item, (dict, list, tuple)):
            nested = telemetry_projection(item, protected=protected)
            if nested:
                output[key] = nested
        elif field in _SAFE_ROUTING and isinstance(item, (str, int, float, bool)):
            output[key] = item if not isinstance(item, str) else item[:120]
        elif not protected and isinstance(item, (str, int, float, bool)):
            output[key] = item if not isinstance(item, str) else item[:120]
    return output


def safe_exception(exc: Exception) -> RuntimeError:
    """Keep exception class identity while preventing exception text capture."""
    return RuntimeError(f"tool failure: {type(exc).__name__}")


__all__ = ["safe_exception", "telemetry_projection"]
