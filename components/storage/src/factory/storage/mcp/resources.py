"""MCP Resource registration for Storage brick.

Resources expose static/queryable data:
- Schemas for storage types
- Documentation on backends
- Live health and status info
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


STORAGE_SCHEMAS = {
    "blob": """
# Blob Storage Interface

## Methods
- `put(key, data, content_type, metadata)` → BlobMetadata
- `get(key)` → (bytes, BlobMetadata)
- `delete(key)` → bool
- `exists(key)` → bool
- `list_keys(prefix, limit)` → list[BlobMetadata]

## Backends
- `local` - Local filesystem
- `s3` - Amazon S3
""",
    "document": """
# Document Storage Interface

## Methods
- `insert(collection, data, doc_id)` → Document
- `get(collection, doc_id)` → Document | None
- `update(collection, doc_id, data)` → Document | None
- `delete(collection, doc_id)` → bool
- `find(collection, query, limit, skip)` → list[Document]
- `count(collection, query)` → int

## Backends
- `tinydb` - TinyDB (file-based)
- `mongodb` - MongoDB
""",
    "sql": """
# SQL Storage Interface

## Methods
- `execute(query, params)` → SQLResult
- `execute_many(query, params_list)` → int
- `fetch_one(query, params)` → dict | None
- `fetch_all(query, params)` → list[dict]
- `table_exists(table_name)` → bool

## Backends
- `sqlite` - SQLite
- `postgres` - PostgreSQL
""",
}


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register all Storage resources with the MCP server."""
    from ..runtime.runtime import StorageRuntime

    @mcp.resource("storage://backends")
    def list_backends() -> str:
        """List available storage backends."""
        backends = StorageRuntime.available_backends()
        return json.dumps({"backends": backends}, indent=2)

    @mcp.resource("storage://health")
    def storage_health() -> str:
        """Get health status of all active storage backends."""
        runtime = get_runtime()
        health = runtime.health_check()
        if not health:
            return json.dumps({"message": "No active storage backends."})
        return json.dumps({
            "stores": {
                k: {"healthy": v.healthy, "backend": v.backend, "latency_ms": v.latency_ms}
                for k, v in health.items()
            },
            "all_healthy": all(h.healthy for h in health.values()),
        }, indent=2)

    @mcp.resource("storage://schema/{storage_type}")
    def storage_schema(storage_type: str) -> str:
        """Get the schema/interface for a storage type."""
        if storage_type in STORAGE_SCHEMAS:
            return STORAGE_SCHEMAS[storage_type]
        available = list(STORAGE_SCHEMAS.keys())
        return f"Unknown storage type: {storage_type}. Available: {available}"
