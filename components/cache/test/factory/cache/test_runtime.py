"""Tests for cache runtime."""

import pytest

from factory.cache.runtime.runtime import CacheRuntime, get_runtime, reset_runtime


class TestCacheRuntime:
    """Tests for CacheRuntime."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset global runtime before each test."""
        reset_runtime()

    def test_available_backends(self) -> None:
        """Test listing available backends."""
        backends = CacheRuntime.available_backends()
        assert "memory" in backends
        assert "redis" in backends

    def test_get_memory_cache(self) -> None:
        """Test getting a memory cache."""
        runtime = CacheRuntime()
        cache = runtime.get_cache("memory")

        cache.set("test", "value")
        assert cache.get("test") == "value"

    def test_cache_caching(self) -> None:
        """Test that caches are cached."""
        runtime = CacheRuntime()

        cache1 = runtime.get_cache("memory")
        cache2 = runtime.get_cache("memory")

        assert cache1 is cache2

    def test_health_check_empty(self) -> None:
        """Test health check with no active caches."""
        runtime = CacheRuntime()
        health = runtime.health_check()
        assert health == {}

    def test_health_check_with_cache(self) -> None:
        """Test health check with active cache."""
        runtime = CacheRuntime()
        runtime.get_cache("memory")

        health = runtime.health_check()
        assert len(health) == 1

    def test_unknown_backend_raises(self) -> None:
        """Test that unknown backends raise ValueError."""
        runtime = CacheRuntime()

        with pytest.raises(ValueError, match="Unknown cache backend"):
            runtime.get_cache("unknown")

    def test_global_runtime(self) -> None:
        """Test global runtime singleton."""
        runtime1 = get_runtime()
        runtime2 = get_runtime()
        assert runtime1 is runtime2

        reset_runtime()
        runtime3 = get_runtime()
        assert runtime3 is not runtime1
