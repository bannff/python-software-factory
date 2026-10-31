"""ElastiCache (Redis-compatible) backend for AWS cache adapter."""

from __future__ import annotations

import fnmatch
import json
import time
from typing import Any

from factory.cache.runtime.ports import CacheHealth, CacheStats


def _require_redis() -> None:
    try:
        import redis  # noqa: F401
    except ImportError:
        msg = "pip install redis — required for ElastiCache backend"
        raise ImportError(msg)


class ElastiCacheBackend:
    """ElastiCache Serverless (Redis-compatible) cache backend."""

    def __init__(
        self,
        endpoint: str = "localhost",
        port: int = 6379,
        ssl: bool = True,
        prefix: str = "factory:",
        **kwargs: Any,
    ) -> None:
        _require_redis()
        import redis as _redis

        self._prefix = prefix
        self._cache_name = kwargs.get("cache_name", "factory-cache")
        self._client = _redis.Redis(
            host=endpoint, port=port, ssl=ssl,
            decode_responses=True,
        )
        self._hits = 0
        self._misses = 0

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any | None:
        raw = self._client.get(self._key(key))
        if raw is None:
            self._misses += 1
            return None
        self._hits += 1
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        raw = json.dumps(value)
        if ttl_seconds:
            self._client.setex(self._key(key), ttl_seconds, raw)
        else:
            self._client.set(self._key(key), raw)
        return True

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(self._key(key)))

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(self._key(key)))

    def clear(self) -> int:
        keys = self._client.keys(f"{self._prefix}*")
        if keys:
            return self._client.delete(*keys)
        return 0

    def keys(self, pattern: str = "*") -> list[str]:
        prefix_len = len(self._prefix)
        raw_keys = self._client.keys(f"{self._prefix}{pattern}")
        return [k[prefix_len:] for k in raw_keys]

    def ttl(self, key: str) -> int | None:
        val = self._client.ttl(self._key(key))
        return val if val and val > 0 else None

    def stats(self) -> CacheStats:
        keys = self._client.keys(f"{self._prefix}*")
        return CacheStats(
            hits=self._hits, misses=self._misses, size=len(keys),
        )

    def health_check(self) -> CacheHealth:
        start = time.time()
        try:
            self._client.ping()
            latency = (time.time() - start) * 1000
            return CacheHealth(
                healthy=True, backend="elasticache",
                latency_ms=latency,
            )
        except Exception as e:
            return CacheHealth(
                healthy=False, backend="elasticache", message=str(e),
            )

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "elasticache",
            "construct": "CfnServerlessCache",
            "props": {
                "engine": "redis",
                "serverless_cache_name": self._cache_name,
            },
        }
