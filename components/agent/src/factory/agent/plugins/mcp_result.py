"""Small Agent-local normalizers for typed and serialized MCP results."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_ENVELOPE_KEYS = frozenset({
    "schema_version", "ok", "data", "error", "idempotency_key",
})


def successful_data(result: Any) -> Any | None:
    """Return successful MCP data from a live result or strict v1 envelope."""
    if isinstance(result, Mapping):
        if (
            set(result) - _ENVELOPE_KEYS
            or result.get("schema_version") != "v1"
            or result.get("ok") is not True
            or result.get("error") is not None
            or "data" not in result
        ):
            return None
        return result["data"]
    if (
        getattr(result, "schema_version", None) != "v1"
        or getattr(result, "ok", None) is not True
        or getattr(result, "error", None) is not None
    ):
        return None
    return getattr(result, "data", None)


def field(value: Any, name: str, default: Any = None) -> Any:
    """Read a field from a mapping or typed data object."""
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def record(value: Any) -> dict[str, Any] | None:
    """Convert one mapping or Pydantic model into a plain memory record."""
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    candidate = model_dump(mode="json") if callable(model_dump) else None
    return dict(candidate) if isinstance(candidate, Mapping) else None
