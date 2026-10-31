"""Abstract ports for cache brick.

Ports define what capabilities the cache needs, not how they're implemented.
Adapters plug in specific backends (memory, Redis, Memcached, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CacheHealth:
    """Health status for a cache backend."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """Statistics for a cache."""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int | None = None

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheStore(Protocol):
    """Port: Key-value cache with TTL support."""

    def get(self, key: str) -> Any | None:
        """Get a value by key. Returns None if not found or expired."""
        ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set a key-value pair with optional TTL. Returns True on success."""
        ...

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        ...

    def clear(self) -> int:
        """Clear all keys. Returns number of keys cleared."""
        ...

    def keys(self, pattern: str = "*") -> list[str]:
        """List keys matching a pattern."""
        ...

    def ttl(self, key: str) -> int | None:
        """Get remaining TTL for a key. Returns None if no TTL or key doesn't exist."""
        ...

    def stats(self) -> CacheStats:
        """Get cache statistics."""
        ...

    def health_check(self) -> CacheHealth:
        """Check cache health."""
        ...
