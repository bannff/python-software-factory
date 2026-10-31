"""Tests for ElastiCache (Redis-compatible) cache backend.

All redis calls are mocked — no real ElastiCache needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from factory.cache.runtime.ports import CacheHealth, CacheStats


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client."""
    return MagicMock()


@pytest.fixture
def backend(mock_redis: MagicMock):
    """Create ElastiCacheBackend with mocked redis."""
    with patch("redis.Redis", return_value=mock_redis):
        from factory.cache.runtime.adapters.backends.elasticache import (
            ElastiCacheBackend,
        )

        return ElastiCacheBackend(endpoint="test-host", port=6379)


class TestElastiCacheGet:
    """get() method tests."""

    def test_get_existing(self, backend, mock_redis: MagicMock) -> None:
        """Returns deserialized value for existing key."""
        mock_redis.get.return_value = json.dumps({"x": 1})
        assert backend.get("k") == {"x": 1}
        mock_redis.get.assert_called_once_with("factory:k")

    def test_get_missing(self, backend, mock_redis: MagicMock) -> None:
        """Returns None for missing key."""
        mock_redis.get.return_value = None
        assert backend.get("nope") is None

    def test_get_tracks_hits_misses(self, backend, mock_redis: MagicMock) -> None:
        """Tracks hit/miss counters."""
        mock_redis.get.side_effect = [json.dumps("v"), None]
        backend.get("hit")
        backend.get("miss")
        s = backend.stats()
        assert s.hits == 1
        assert s.misses == 1


class TestElastiCacheSet:
    """set() method tests."""

    def test_set_without_ttl(self, backend, mock_redis: MagicMock) -> None:
        """Calls redis.set without expiry."""
        assert backend.set("k", "v") is True
        mock_redis.set.assert_called_once_with("factory:k", json.dumps("v"))

    def test_set_with_ttl(self, backend, mock_redis: MagicMock) -> None:
        """Calls redis.setex with TTL."""
        backend.set("k", "v", ttl_seconds=30)
        mock_redis.setex.assert_called_once_with("factory:k", 30, json.dumps("v"))


class TestElastiCacheOps:
    """delete, exists, clear, keys, ttl."""

    def test_delete(self, backend, mock_redis: MagicMock) -> None:
        """delete() delegates to redis.delete."""
        mock_redis.delete.return_value = 1
        assert backend.delete("k") is True

    def test_exists(self, backend, mock_redis: MagicMock) -> None:
        """exists() delegates to redis.exists."""
        mock_redis.exists.return_value = 1
        assert backend.exists("k") is True

    def test_clear_with_keys(self, backend, mock_redis: MagicMock) -> None:
        """clear() deletes all prefixed keys."""
        mock_redis.keys.return_value = ["factory:a", "factory:b"]
        mock_redis.delete.return_value = 2
        assert backend.clear() == 2

    def test_clear_empty(self, backend, mock_redis: MagicMock) -> None:
        """clear() returns 0 when no keys exist."""
        mock_redis.keys.return_value = []
        assert backend.clear() == 0

    def test_keys_strips_prefix(self, backend, mock_redis: MagicMock) -> None:
        """keys() strips the prefix from returned keys."""
        mock_redis.keys.return_value = ["factory:a", "factory:b"]
        assert backend.keys("*") == ["a", "b"]

    def test_ttl_positive(self, backend, mock_redis: MagicMock) -> None:
        """ttl() returns positive remaining time."""
        mock_redis.ttl.return_value = 42
        assert backend.ttl("k") == 42

    def test_ttl_no_expiry(self, backend, mock_redis: MagicMock) -> None:
        """ttl() returns None for keys without TTL."""
        mock_redis.ttl.return_value = -1
        assert backend.ttl("k") is None


class TestElastiCacheHealth:
    """health_check() and infrastructure_spec()."""

    def test_health_check_healthy(self, backend, mock_redis: MagicMock) -> None:
        """Healthy when ping succeeds."""
        mock_redis.ping.return_value = True
        h = backend.health_check()
        assert isinstance(h, CacheHealth)
        assert h.healthy is True
        assert h.backend == "elasticache"

    def test_health_check_failure(self, backend, mock_redis: MagicMock) -> None:
        """Unhealthy when ping raises."""
        mock_redis.ping.side_effect = ConnectionError("refused")
        h = backend.health_check()
        assert h.healthy is False
        assert "refused" in h.message

    def test_infrastructure_spec(self, backend) -> None:
        """Returns valid ElastiCache spec dict."""
        spec = backend.infrastructure_spec()
        assert spec["service"] == "elasticache"
        assert spec["construct"] == "CfnServerlessCache"
        assert spec["props"]["engine"] == "redis"
