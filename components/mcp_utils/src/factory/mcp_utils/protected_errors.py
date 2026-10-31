"""Non-protected error projection that preserves ordinary protocol payloads."""
from __future__ import annotations

import re
from typing import Any

from .protected_content import sanitize_protected_error

_EXCEPTION_KEYS = frozenset({
    "error", "error_message", "exception", "exception_message", "exception_text",
    "stack_trace", "traceback",
})


def _field_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", value)
    return re.sub(r"[^A-Za-z0-9]+", "_", snake).strip("_").lower()


def _error(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "operation failed"
                if _field_name(key) in {"message", "detail", "reason"}
                and isinstance(item, str)
                else _error(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_error(item) for item in value]
    return sanitize_protected_error(value) if isinstance(value, str) else value


def safe_projection(value: Any) -> Any:
    """Sanitize known error containers without changing normal payload fields."""
    if isinstance(value, dict):
        fields = {_field_name(key) for key in value}
        if {"type", "message"} & fields or "code" in fields:
            return _error(value)
        return {
            key: _error(item) if _field_name(key) in _EXCEPTION_KEYS
            else safe_projection(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_projection(item) for item in value]
    return value
