"""AWS adapter for cache brick.

Supports DynamoDB (simple KV+TTL) and ElastiCache (Redis-compatible).
Service is selected at init time via the `service` parameter.
"""

from __future__ import annotations

import json
import time
from typing import Any

from factory.cache.runtime.ports import CacheHealth, CacheStats


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS cache adapter"
        raise ImportError(msg)


class AWSCacheAdapter:
    """AWS adapter — delegates to DynamoDB or ElastiCache backend."""

    def __init__(self, service: str = "dynamodb", **config: Any) -> None:
        _require_boto3()
        self._service = service
        match service:
            case "dynamodb":
                from .backends.dynamodb import DynamoDBBackend
                self._backend = DynamoDBBackend(**config)
            case "elasticache":
                from .backends.elasticache import ElastiCacheBackend
                self._backend = ElastiCacheBackend(**config)
            case _:
                raise ValueError(f"Unknown AWS cache service: {service}")

    def get(self, key: str) -> Any | None:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        return self._backend.set(key, value, ttl_seconds)

    def delete(self, key: str) -> bool:
        return self._backend.delete(key)

    def exists(self, key: str) -> bool:
        return self._backend.exists(key)

    def clear(self) -> int:
        return self._backend.clear()

    def keys(self, pattern: str = "*") -> list[str]:
        return self._backend.keys(pattern)

    def ttl(self, key: str) -> int | None:
        return self._backend.ttl(key)

    def stats(self) -> CacheStats:
        return self._backend.stats()

    def health_check(self) -> CacheHealth:
        return self._backend.health_check()

    def infrastructure_spec(self) -> dict[str, Any]:
        """Return AWS resource requirements for this adapter."""
        return self._backend.infrastructure_spec()
