"""Tests for environment variable config adapter."""

import os
import pytest

from factory.config.runtime.adapters.env_adapter import EnvConfigStore


class TestEnvConfigStore:
    """Tests for EnvConfigStore adapter."""

    @pytest.fixture
    def config(self) -> EnvConfigStore:
        """Create an env config store with test prefix."""
        return EnvConfigStore(prefix="TEST_CONFIG_")

    @pytest.fixture(autouse=True)
    def cleanup(self) -> None:
        """Clean up test env vars after each test."""
        yield
        # Remove any test env vars
        to_remove = [k for k in os.environ if k.startswith("TEST_CONFIG_")]
        for k in to_remove:
            del os.environ[k]

    def test_get_set(self, config: EnvConfigStore) -> None:
        """Test basic get/set."""
        config.set("key1", "value1")
        assert config.get("key1") == "value1"

    def test_get_missing(self, config: EnvConfigStore) -> None:
        """Test getting a missing key."""
        assert config.get("missing") is None
        assert config.get("missing", "default") == "default"

    def test_get_typed_int(self, config: EnvConfigStore) -> None:
        """Test getting typed integer."""
        config.set("port", "8080")
        assert config.get_typed("port", int) == 8080
        assert config.get_typed("missing", int, 3000) == 3000

    def test_get_typed_bool(self, config: EnvConfigStore) -> None:
        """Test getting typed boolean."""
        config.set("enabled", "true")
        assert config.get_typed("enabled", bool) is True

        config.set("disabled", "false")
        assert config.get_typed("disabled", bool) is False

        config.set("yes", "1")
        assert config.get_typed("yes", bool) is True

    def test_delete(self, config: EnvConfigStore) -> None:
        """Test deleting a key."""
        config.set("to_delete", "value")
        assert config.exists("to_delete")

        assert config.delete("to_delete")
        assert not config.exists("to_delete")

    def test_delete_missing(self, config: EnvConfigStore) -> None:
        """Test deleting a missing key."""
        assert not config.delete("missing")

    def test_exists(self, config: EnvConfigStore) -> None:
        """Test checking existence."""
        assert not config.exists("key")
        config.set("key", "value")
        assert config.exists("key")

    def test_keys(self, config: EnvConfigStore) -> None:
        """Test listing keys."""
        config.set("app.name", "test")
        config.set("app.version", "1.0")
        config.set("db.host", "localhost")

        all_keys = config.keys()
        assert len(all_keys) == 3

        app_keys = config.keys("app")
        assert len(app_keys) == 2

    def test_get_all(self, config: EnvConfigStore) -> None:
        """Test getting all values."""
        config.set("a", "1")
        config.set("b", "2")

        all_values = config.get_all()
        assert len(all_values) == 2
        assert all_values["a"] == "1"

    def test_health_check(self, config: EnvConfigStore) -> None:
        """Test health check."""
        health = config.health_check()
        assert health.healthy
        assert health.backend == "env"

    def test_key_conversion(self, config: EnvConfigStore) -> None:
        """Test that keys are converted to env var format."""
        config.set("database.host", "localhost")
        # Should be stored as TEST_CONFIG_DATABASE_HOST
        assert os.environ.get("TEST_CONFIG_DATABASE_HOST") == "localhost"
