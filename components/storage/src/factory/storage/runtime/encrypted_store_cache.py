"""Shared getter for cached, encrypted-at-rest SQLite stores.

``get_protected_artifact_store``, ``get_credential_slot_store``, and
``get_owner_secret_store`` all repeat the same shape: default a db_path from
config, default ``keys`` to ``LocalEnvironmentKeyProvider``, cache by db_path,
construct the adapter class on first use. This extracts that shape once so
``StorageRuntime`` stays a thin per-store dispatcher.
"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")


def get_or_create_encrypted_store(
    cache: dict[str, T], db_path: str, default_path: str,
    adapter: Callable[..., T], **kwargs: Any,
) -> T:
    """Return the cached store at ``db_path`` (or ``default_path``), creating it."""
    db_path = db_path or default_path
    if "keys" not in kwargs:
        from factory.mcp_utils.interface import LocalEnvironmentKeyProvider
        kwargs["keys"] = LocalEnvironmentKeyProvider()
    if db_path not in cache:
        cache[db_path] = adapter(db_path, **kwargs)
    return cache[db_path]


__all__ = ["get_or_create_encrypted_store"]
