"""Cache core - high-level convenience functions."""

from __future__ import annotations

from typing import Any

from .runtime.runtime import get_runtime


def cache_get(key: str) -> Any | None:
    """Get a value from the default cache."""
    return get_runtime().get_cache().get(key)


def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> bool:
    """Set a value in the default cache."""
    return get_runtime().get_cache().set(key, value, ttl_seconds)


def cache_delete(key: str) -> bool:
    """Delete a key from the default cache."""
    return get_runtime().get_cache().delete(key)


def cache_clear() -> int:
    """Clear the default cache."""
    return get_runtime().get_cache().clear()
