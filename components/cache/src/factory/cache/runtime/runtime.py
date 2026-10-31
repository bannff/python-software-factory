"""Cache runtime factory - selects and configures cache adapters.

Usage:
    runtime = CacheRuntime()
    cache = runtime.get_cache("memory")  # or "redis" or "aws"
"""

from __future__ import annotations

import logging
from typing import Any

from .ports import CacheStore, CacheHealth

logger = logging.getLogger(__name__)


class CacheRuntime:
    """Factory for creating cache adapters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._caches: dict[str, CacheStore] = {}

    def get_cache(self, backend: str = "memory", **kwargs: Any) -> CacheStore:
        """Get or create a cache adapter."""
        cache_key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if cache_key not in self._caches:
            self._caches[cache_key] = self._create_cache(backend, **kwargs)
        return self._caches[cache_key]

    def _create_cache(self, backend: str, **kwargs: Any) -> CacheStore:
        """Create a cache adapter."""
        if backend == "memory":
            from .adapters.memory_adapter import MemoryCacheStore
            return MemoryCacheStore(**kwargs)
        elif backend == "redis":
            from .adapters.redis_adapter import RedisCacheStore
            return RedisCacheStore(**kwargs)
        elif backend == "aws":
            from .adapters.aws import AWSCacheAdapter
            return AWSCacheAdapter(**kwargs)
        raise ValueError(f"Unknown cache backend: {backend}. Available: memory, redis, aws")

    def health_check(self) -> dict[str, CacheHealth]:
        """Check health of all active caches."""
        return {name: cache.health_check() for name, cache in self._caches.items()}

    @staticmethod
    def available_backends() -> list[str]:
        """List available cache backends."""
        return ["memory", "redis", "aws"]


# Global runtime instance
_runtime: CacheRuntime | None = None


def get_runtime() -> CacheRuntime:
    """Get the global cache runtime."""
    global _runtime
    if _runtime is None:
        from factory.mcp_utils.config_helpers import get_infra
        backend = get_infra("cache.backend", "memory")
        _runtime = CacheRuntime()
        _runtime.get_cache(backend)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
