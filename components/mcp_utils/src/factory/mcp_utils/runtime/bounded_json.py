"""Bounded JSON helpers for typed MCP evidence envelopes."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from math import isfinite
from typing import Any

from pydantic import BaseModel

_MAX_OBJECT_KEYS = 256
_MAX_SEQUENCE_ITEMS = 1_024
_MAX_NESTING = 12
_MAX_STRING_LENGTH = 65_536
_MAX_INTEGER = 1_000_000_000
_MAX_BYTES = 1_048_576


def to_plain_json(value: Any) -> Any:
    """Convert nested Pydantic models and containers without coercing numbers."""
    if isinstance(value, BaseModel):
        return to_plain_json(value.model_dump(mode="python"))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return [to_plain_json(item) for item in sorted(value, key=str)]
    if isinstance(value, Mapping):
        return {key: to_plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_json(item) for item in value]
    return value


def is_bounded_json(
    value: Any, *, max_sequence_items: int = _MAX_SEQUENCE_ITEMS,
) -> bool:
    """Return whether value is finite JSON within the shared evidence limits."""
    return _json_safe(value, max_sequence_items=max_sequence_items) and _json_size_ok(value)


def _json_safe(
    value: Any, depth: int = 0, *, max_sequence_items: int = _MAX_SEQUENCE_ITEMS,
) -> bool:
    if depth > _MAX_NESTING:
        return False
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        return len(value) <= _MAX_STRING_LENGTH
    if isinstance(value, int):
        return abs(value) <= _MAX_INTEGER
    if isinstance(value, float):
        return isfinite(value)
    if isinstance(value, Mapping):
        return len(value) <= _MAX_OBJECT_KEYS and all(
            isinstance(key, str)
            and len(key) <= _MAX_STRING_LENGTH
            and _json_safe(item, depth + 1, max_sequence_items=max_sequence_items)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return len(value) <= max_sequence_items and all(
            _json_safe(item, depth + 1, max_sequence_items=max_sequence_items)
            for item in value
        )
    return False


def _json_size_ok(value: Any) -> bool:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError):
        return False
    return len(encoded.encode("utf-8")) <= _MAX_BYTES


__all__ = ["is_bounded_json", "to_plain_json"]
