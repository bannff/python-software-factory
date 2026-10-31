"""MCP Prompt registration for Storage brick.

Prompts provide guided workflows for common tasks:
- Setting up storage backends
- Migrating between backends
- Troubleshooting storage issues
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register all Storage prompts with the MCP server."""

    @mcp.prompt()
    def setup_storage(storage_type: str, backend: str) -> str:
        """Guide for setting up a storage backend."""
        return f"""# Setting Up {storage_type.title()} Storage with {backend}

## 1. Configuration

Configure the storage backend in your application:

```python
from factory.storage.runtime.runtime import StorageRuntime

runtime = StorageRuntime()
store = runtime.get_{storage_type}_store(backend="{backend}")
```

## 2. Health Check

Verify the backend is working:

```python
health = store.health_check()
print(f"Healthy: {{health.healthy}}, Latency: {{health.latency_ms}}ms")
```

## 3. Basic Operations

Use the MCP tools to interact with storage:
- `{storage_type}_*` tools for CRUD operations
- `storage://health` resource for monitoring

## 4. Best Practices

- Always check health before critical operations
- Use appropriate backend for your use case:
  - Development: local/tinydb/sqlite
  - Production: s3/mongodb/postgres
- For graph storage, use the `graph` brick instead
"""

    @mcp.prompt()
    def migrate_storage(from_backend: str, to_backend: str) -> str:
        """Guide for migrating between storage backends."""
        return f"""# Migrating from {from_backend} to {to_backend}

## Steps

1. **Create both stores** - Initialize source and target
2. **Export from source** - List and retrieve all data
3. **Import to target** - Insert data into new backend
4. **Validate** - Compare counts and spot-check records

## Rollback Plan

Keep the source store active until migration is verified.
"""

    @mcp.prompt()
    def storage_troubleshooting() -> str:
        """Guide for troubleshooting storage issues."""
        return """# Storage Troubleshooting Guide

## Common Issues

### Connection Failures
1. Check health: `health_check()` tool
2. Verify connection string/credentials
3. Check network connectivity

### Performance Issues
1. Check latency in health check
2. Add indexes for frequent queries
3. Consider caching layer

### Data Issues
1. Verify data format matches schema
2. Check for encoding issues (UTF-8)
3. Validate document/record IDs
"""
