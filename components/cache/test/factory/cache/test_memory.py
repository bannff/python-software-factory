"""Tests for memory cache adapter."""

import pytest
import time

from factory.cache.runtime.adapters.memory_adapter import MemoryCacheStore


class TestMemoryCacheStore:
    """Tests for MemoryCacheStore adapter."""

    @pytest.fixture
    def cache(self) -> MemoryCacheStore:
        """Create a memory cache."""
        return MemoryCacheStore()

    def test_get_set(self, cache: MemoryCacheStore) -> None:
        """Test basic get/set."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self, cache: MemoryCacheStore) -> None:
        """Test getting a missing key."""
        assert cache.get("missing") is None

    def test_set_with_ttl(self, cache: MemoryCacheStore) -> None:
        """Test setting with TTL."""
        cache.set("expiring", "value", ttl_seconds=1)
        assert cache.get("expiring") == "value"
        time.sleep(1.1)
        assert cache.get("expiring") is None

    def test_delete(self, cache: MemoryCacheStore) -> None:
        """Test deleting a key."""
        cache.set("to_delete", "value")
        assert cache.delete("to_delete")
        assert cache.get("to_delete") is None

    def test_delete_missing(self, cache: MemoryCacheStore) -> None:
        """Test deleting a missing key."""
        assert not cache.delete("missing")

    def test_exists(self, cache: MemoryCacheStore) -> None:
        """Test checking existence."""
        assert not cache.exists("key")
        cache.set("key", "value")
        assert cache.exists("key")

    def test_clear(self, cache: MemoryCacheStore) -> None:
        """Test clearing cache."""
        cache.set("a", 1)
        cache.set("b", 2)
        cleared = cache.clear()
        assert cleared == 2
        assert cache.get("a") is None

    def test_keys(self, cache: MemoryCacheStore) -> None:
        """Test listing keys."""
        cache.set("user:1", "alice")
        cache.set("user:2", "bob")
        cache.set("item:1", "thing")

        all_keys = cache.keys()
        assert len(all_keys) == 3

        user_keys = cache.keys("user:*")
        assert len(user_keys) == 2

    def test_ttl(self, cache: MemoryCacheStore) -> None:
        """Test getting TTL."""
        cache.set("no_ttl", "value")
        assert cache.ttl("no_ttl") is None

        cache.set("with_ttl", "value", ttl_seconds=10)
        ttl = cache.ttl("with_ttl")
        assert ttl is not None
        assert 8 <= ttl <= 10

    def test_stats(self, cache: MemoryCacheStore) -> None:
        """Test cache statistics."""
        cache.set("key", "value")
        cache.get("key")  # hit
        cache.get("missing")  # miss

        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.size == 1
        assert stats.hit_rate == 0.5

    def test_health_check(self, cache: MemoryCacheStore) -> None:
        """Test health check."""
        health = cache.health_check()
        assert health.healthy
        assert health.backend == "memory"

    def test_max_size_eviction(self) -> None:
        """Test eviction when max size is reached."""
        cache = MemoryCacheStore(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # Should evict 'a'

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_complex_values(self, cache: MemoryCacheStore) -> None:
        """Test storing complex values."""
        cache.set("dict", {"name": "test", "count": 42})
        cache.set("list", [1, 2, 3])

        assert cache.get("dict") == {"name": "test", "count": 42}
        assert cache.get("list") == [1, 2, 3]
