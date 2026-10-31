"""Redis cache adapter."""

from __future__ import annotations

import importlib.util
import json
import time
from typing import Any

from factory.cache.runtime.ports import CacheHealth, CacheStats

REDIS_AVAILABLE = importlib.util.find_spec("redis") is not None


def _require_redis() -> None:
    if not REDIS_AVAILABLE:
        raise ImportError("redis required. Install with: pip install redis")


class RedisCacheStore:
    """Redis implementation of CacheStore port."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        prefix: str = "factory:",
        **kwargs: Any,
    ) -> None:
        _require_redis()
        import redis
        self._client = redis.from_url(url, **kwargs)
        self._prefix = prefix
        self._hits = 0
        self._misses = 0

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any | None:
        """Get a value by key."""
        value = self._client.get(self._key(key))
        if value is None:
            self._misses += 1
            return None
        self._hits += 1
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set a key-value pair with optional TTL."""
        serialized = json.dumps(value)
        if ttl_seconds:
            self._client.setex(self._key(key), ttl_seconds, serialized)
        else:
            self._client.set(self._key(key), serialized)
        return True

    def delete(self, key: str) -> bool:
        """Delete a key."""
        return self._client.delete(self._key(key)) > 0

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return self._client.exists(self._key(key)) > 0

    def clear(self) -> int:
        """Clear all keys with our prefix."""
        pattern = f"{self._prefix}*"
        keys = self._client.keys(pattern)
        if keys:
            return self._client.delete(*keys)
        return 0

    def keys(self, pattern: str = "*") -> list[str]:
        """List keys matching a pattern."""
        full_pattern = f"{self._prefix}{pattern}"
        keys = self._client.keys(full_pattern)
        prefix_len = len(self._prefix)
        return [k.decode()[prefix_len:] if isinstance(k, bytes) else k[prefix_len:] for k in keys]

    def ttl(self, key: str) -> int | None:
        """Get remaining TTL for a key."""
        ttl = self._client.ttl(self._key(key))
        return ttl if ttl > 0 else None

    def stats(self) -> CacheStats:
        """Get cache statistics."""
        size = len(self.keys())
        return CacheStats(hits=self._hits, misses=self._misses, size=size)

    def health_check(self) -> CacheHealth:
        """Check Redis health."""
        start = time.time()
        try:
            self._client.ping()
            latency = (time.time() - start) * 1000
            info = self._client.info("memory")
            return CacheHealth(
                healthy=True, backend="redis", latency_ms=latency,
                details={"used_memory": info.get("used_memory_human", "unknown")},
            )
        except Exception as e:
            return CacheHealth(healthy=False, backend="redis", message=str(e))
