"""MCP Resource registration for Cache brick.

Resources expose static/queryable data:
- Schemas for configuration and cache entries
- Documentation on adapters and patterns
- Live statistics and backend info
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING, Callable

from .docs import CACHE_DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import CacheRuntime


def register(mcp: Any, get_runtime: Callable[[], "CacheRuntime"]) -> None:
    """Register all Cache resources with the MCP server."""
    from ..runtime.ports import CacheStats, CacheHealth

    # Schema resources
    @mcp.resource("cache://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for cache configuration."""
        schema = {
            "type": "object",
            "properties": {
                "backend": {"type": "string", "enum": ["memory", "redis"]},
                "url": {"type": "string", "description": "Redis URL"},
                "max_size": {"type": "integer", "description": "Max entries"},
                "prefix": {"type": "string", "description": "Key prefix"},
            },
        }
        return json.dumps(schema, indent=2)

    @mcp.resource("cache://schemas/entry")
    def resource_entry_schema() -> str:
        """Get the JSON schema for cache entries."""
        schema = {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Cache key"},
                "value": {"type": "any", "description": "Cached value"},
                "ttl_seconds": {"type": "integer", "description": "Time-to-live"},
            },
            "required": ["key", "value"],
        }
        return json.dumps(schema, indent=2)

    @mcp.resource("cache://schemas/stats")
    def resource_stats_schema() -> str:
        """Get the JSON schema for cache statistics."""
        schema = {
            "type": "object",
            "properties": {
                "hits": {"type": "integer"},
                "misses": {"type": "integer"},
                "hit_rate": {"type": "number"},
                "size": {"type": "integer"},
                "max_size": {"type": "integer", "nullable": True},
            },
        }
        return json.dumps(schema, indent=2)

    # Documentation resources
    @mcp.resource("cache://docs")
    def resource_docs_list() -> str:
        """List available cache documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in CACHE_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("cache://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get cache documentation by name."""
        if doc_name in CACHE_DOCS:
            return CACHE_DOCS[doc_name]["content"]
        available = list(CACHE_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    # Live data resources
    @mcp.resource("cache://stats")
    def resource_stats() -> str:
        """Get current cache statistics."""
        runtime = get_runtime()
        cache = runtime.get_cache()
        stats = cache.stats()
        return json.dumps({
            "hits": stats.hits,
            "misses": stats.misses,
            "hit_rate": stats.hit_rate,
            "size": stats.size,
            "max_size": stats.max_size,
        }, indent=2)

    @mcp.resource("cache://backends")
    def resource_backends() -> str:
        """List available cache backends."""
        from ..runtime.runtime import CacheRuntime

        backends = CacheRuntime.available_backends()
        return json.dumps({
            "backends": [
                {"name": "memory", "description": "In-memory LRU cache"},
                {"name": "redis", "description": "Distributed Redis cache"},
            ],
            "available": backends,
        }, indent=2)

    @mcp.resource("cache://health")
    def resource_health() -> str:
        """Get cache health status."""
        runtime = get_runtime()
        health = runtime.health_check()
        return json.dumps({
            "caches": {
                k: {"healthy": v.healthy, "backend": v.backend, "message": v.message}
                for k, v in health.items()
            },
            "all_healthy": all(h.healthy for h in health.values()) if health else True,
        }, indent=2)

    # Cross-reference to factory
    @mcp.resource("cache://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"],
            "related_bricks": {
                "workflow": "Uses cache for step result caching",
                "auth": "Uses cache for session storage",
            },
        }, indent=2)
