"""Tests for config runtime."""

import os
import pytest

from factory.config.runtime.runtime import ConfigRuntime, get_runtime, reset_runtime


class TestConfigRuntime:
    """Tests for ConfigRuntime."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset global runtime before each test."""
        reset_runtime()
        yield
        # Clean up test env vars
        to_remove = [k for k in os.environ if k.startswith("FACTORY_")]
        for k in to_remove:
            del os.environ[k]

    def test_available_backends(self) -> None:
        """Test listing available backends."""
        backends = ConfigRuntime.available_backends()
        assert "env" in backends
        assert "file" in backends
        assert "ssm" in backends

    def test_get_env_config(self) -> None:
        """Test getting an env config."""
        runtime = ConfigRuntime()
        config = runtime.get_config("env")

        config.set("test", "value")
        assert config.get("test") == "value"

    def test_config_caching(self) -> None:
        """Test that configs are cached."""
        runtime = ConfigRuntime()

        config1 = runtime.get_config("env")
        config2 = runtime.get_config("env")

        assert config1 is config2

    def test_environment(self) -> None:
        """Test environment property."""
        runtime = ConfigRuntime(environment="production")
        assert runtime.environment == "production"

    def test_layered_config(self, tmp_path) -> None:
        """Test layered configuration."""
        runtime = ConfigRuntime()

        # Add env layer
        env_config = runtime.get_config("env", prefix="LAYER_")
        env_config.set("key", "from_env")
        runtime.add_layer(env_config)

        # Add file layer (overrides env)
        file_config = runtime.get_config("file", path=str(tmp_path / "layer.yaml"))
        file_config.set("key", "from_file")
        runtime.add_layer(file_config)

        # File layer should win
        assert runtime.get_layered("key") == "from_file"

        # Clean up
        os.environ.pop("LAYER_KEY", None)

    def test_health_check_empty(self) -> None:
        """Test health check with no active configs."""
        runtime = ConfigRuntime()
        health = runtime.health_check()
        assert health == {}

    def test_health_check_with_config(self) -> None:
        """Test health check with active config."""
        runtime = ConfigRuntime()
        runtime.get_config("env")

        health = runtime.health_check()
        assert len(health) == 1

    def test_unknown_backend_raises(self) -> None:
        """Test that unknown backends raise ValueError."""
        runtime = ConfigRuntime()

        with pytest.raises(ValueError, match="Unknown config backend"):
            runtime.get_config("unknown")

    def test_global_runtime(self) -> None:
        """Test global runtime singleton."""
        runtime1 = get_runtime()
        runtime2 = get_runtime()
        assert runtime1 is runtime2

        reset_runtime()
        runtime3 = get_runtime()
        assert runtime3 is not runtime1

    def test_global_runtime_uses_env(self) -> None:
        """Test that global runtime uses FACTORY_ENV."""
        os.environ["FACTORY_ENV"] = "staging"
        reset_runtime()

        runtime = get_runtime()
        assert runtime.environment == "staging"
