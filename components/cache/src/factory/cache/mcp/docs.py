"""Documentation content for cache MCP resources."""

CACHE_DOCS = {
    "overview": {
        "title": "Cache Brick Overview",
        "content": """# Cache Brick

Ephemeral caching with pluggable backends for the Python Factory.

## Core Concepts

- **CacheStore**: Protocol defining cache operations
- **Adapters**: Pluggable backends (memory, Redis)
- **TTL**: Time-to-live support for automatic expiration
- **Stats**: Hit/miss tracking for monitoring

## Quick Start

1. Get a value:
```
cache_get(key="user:123")
```

2. Set a value with TTL:
```
cache_set(key="user:123", value="data", ttl_seconds=3600)
```

3. Check statistics:
```
cache_stats()
```

## Backends

- `memory` - In-memory LRU cache (default)
- `redis` - Redis for distributed caching

## MCP Tools

- `cache_get` - Get value by key
- `cache_set` - Set value with optional TTL
- `cache_delete` - Delete a key
- `cache_keys` - List keys by pattern
- `cache_stats` - Get hit/miss statistics
- `cache_clear` - Clear all entries
""",
    },
    "adapters": {
        "title": "Cache Adapter Documentation",
        "content": """# Cache Adapters

The cache brick uses a ports-and-adapters architecture.

## Memory Adapter

In-memory LRU cache with TTL support.

**Features:**
- Thread-safe operations
- LRU eviction when max_size reached
- TTL-based expiration
- Pattern matching for keys

**Configuration:**
```python
cache = runtime.get_cache("memory", max_size=1000)
```

## Redis Adapter

Distributed cache using Redis.

**Features:**
- Distributed across instances
- Persistent (configurable)
- Native TTL support
- Pattern matching via SCAN

**Configuration:**
```python
cache = runtime.get_cache(
    "redis",
    url="redis://localhost:6379/0",
    prefix="myapp:"
)
```

## Implementing Custom Adapters

Implement the `CacheStore` protocol:

```python
class MyCacheStore:
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def clear(self) -> int: ...
    def keys(self, pattern: str = "*") -> list[str]: ...
    def ttl(self, key: str) -> int | None: ...
    def stats(self) -> CacheStats: ...
    def health_check(self) -> CacheHealth: ...
```
""",
    },
    "patterns": {
        "title": "Cache Usage Patterns",
        "content": """# Cache Usage Patterns

Common patterns for effective caching.

## Cache-Aside Pattern

```python
value = cache_get(key)
if value is None:
    value = expensive_computation()
    cache_set(key, value, ttl_seconds=3600)
```

## Key Naming Conventions

Use hierarchical keys:
- `user:{id}` - User data
- `session:{token}` - Session data
- `config:{name}` - Configuration
- `rate:{ip}:{endpoint}` - Rate limiting

## TTL Guidelines

| Data Type | Suggested TTL |
|-----------|---------------|
| Session | 3600 (1 hour) |
| User profile | 300 (5 min) |
| Config | 60 (1 min) |
| Rate limit | 60 (1 min) |

## Invalidation Strategies

1. **TTL-based**: Let entries expire naturally
2. **Explicit**: Delete on data change
3. **Pattern**: Clear by prefix (`user:*`)
""",
    },
}
