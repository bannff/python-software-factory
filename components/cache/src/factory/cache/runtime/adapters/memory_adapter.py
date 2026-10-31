"""In-memory cache adapter."""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass
from typing import Any

from factory.cache.runtime.ports import CacheHealth, CacheStats


@dataclass
class CacheEntry:
    """A cache entry with optional expiration."""
    value: Any
    expires_at: float | None = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MemoryCacheStore:
    """In-memory implementation of CacheStore port."""

    def __init__(self, max_size: int | None = None) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get a value by key."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set a key-value pair with optional TTL."""
        if self._max_size and len(self._store) >= self._max_size and key not in self._store:
            # Simple eviction: remove oldest expired or first key
            self._evict_one()

        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
        return True

    def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        entry = self._store.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            del self._store[key]
            return False
        return True

    def clear(self) -> int:
        """Clear all keys."""
        count = len(self._store)
        self._store.clear()
        return count

    def keys(self, pattern: str = "*") -> list[str]:
        """List keys matching a pattern."""
        # Clean expired keys first
        self._clean_expired()
        if pattern == "*":
            return list(self._store.keys())
        return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]

    def ttl(self, key: str) -> int | None:
        """Get remaining TTL for a key."""
        entry = self._store.get(key)
        if entry is None or entry.expires_at is None:
            return None
        remaining = entry.expires_at - time.time()
        return max(0, int(remaining)) if remaining > 0 else None

    def stats(self) -> CacheStats:
        """Get cache statistics."""
        self._clean_expired()
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            size=len(self._store),
            max_size=self._max_size,
        )

    def health_check(self) -> CacheHealth:
        """Check cache health."""
        start = time.time()
        try:
            # Simple write/read test
            test_key = "__health_check__"
            self.set(test_key, "ok", ttl_seconds=1)
            self.get(test_key)
            self.delete(test_key)
            latency = (time.time() - start) * 1000
            return CacheHealth(
                healthy=True, backend="memory", latency_ms=latency,
                details={"size": len(self._store)},
            )
        except Exception as e:
            return CacheHealth(healthy=False, backend="memory", message=str(e))

    def _clean_expired(self) -> None:
        """Remove expired entries."""
        expired = [k for k, v in self._store.items() if v.is_expired()]
        for k in expired:
            del self._store[k]

    def _evict_one(self) -> None:
        """Evict one entry (expired first, then oldest)."""
        for k, v in list(self._store.items()):
            if v.is_expired():
                del self._store[k]
                return
        # No expired, remove first key
        if self._store:
            del self._store[next(iter(self._store))]
