"""Public Polylith interface for the storage brick."""
from __future__ import annotations

from typing import Any

from .runtime import BlobStore, SQLStore, StorageRuntime, get_runtime
from .server import create_mcp_server as create_server


def get_sql_store(backend: str = "sqlite", **kwargs: Any) -> SQLStore:
    """Return a configured SQL store through the shared storage runtime."""
    return get_runtime().get_sql_store(backend, **kwargs)


def get_blob_store(backend: str = "local", **kwargs: Any) -> BlobStore:
    """Return a configured blob store through the shared storage runtime."""
    return get_runtime().get_blob_store(backend, **kwargs)


__all__ = [
    "BlobStore", "SQLStore", "StorageRuntime", "create_server", "get_blob_store",
    "get_runtime", "get_sql_store",
]
