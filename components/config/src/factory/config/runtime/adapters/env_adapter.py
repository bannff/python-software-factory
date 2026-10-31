"""Environment variable config adapter."""

from __future__ import annotations

import os
import time
from typing import Any

from factory.config.runtime.ports import ConfigHealth


class EnvConfigStore:
    """Environment variable implementation of ConfigStore port."""

    def __init__(self, prefix: str = "FACTORY_") -> None:
        self._prefix = prefix

    def _key(self, key: str) -> str:
        """Convert key to env var name."""
        return f"{self._prefix}{key.upper().replace('.', '_')}"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from environment."""
        return os.environ.get(self._key(key), default)

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        """Get a configuration value with type coercion."""
        value = self.get(key)
        if value is None:
            return default
        try:
            if value_type == bool:
                return value.lower() in ("true", "1", "yes", "on")
            return value_type(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        """Set an environment variable."""
        os.environ[self._key(key)] = str(value)
        return True

    def delete(self, key: str) -> bool:
        """Delete an environment variable."""
        env_key = self._key(key)
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if an environment variable exists."""
        return self._key(key) in os.environ

    def keys(self, prefix: str = "") -> list[str]:
        """List configuration keys with optional prefix filter."""
        full_prefix = self._key(prefix)
        result = []
        for key in os.environ:
            if key.startswith(self._prefix):
                # Convert back to config key format
                config_key = key[len(self._prefix):].lower().replace("_", ".")
                if not prefix or config_key.startswith(prefix.lower()):
                    result.append(config_key)
        return result

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        """Get all configuration values with optional prefix filter."""
        return {key: self.get(key) for key in self.keys(prefix)}

    def health_check(self) -> ConfigHealth:
        """Check env config health."""
        start = time.time()
        try:
            # Simple read test
            os.environ.get("__health_check__")
            latency = (time.time() - start) * 1000
            return ConfigHealth(
                healthy=True, backend="env", latency_ms=latency,
                details={"prefix": self._prefix, "keys_count": len(self.keys())},
            )
        except Exception as e:
            return ConfigHealth(healthy=False, backend="env", message=str(e))
