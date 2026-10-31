"""Infrastructure environment variable config adapter.

Maps dot-notation keys to uppercase-underscore env vars with NO prefix.
Convention: neo4j.uri → NEO4J_URI, storage.doc.backend → STORAGE_DOC_BACKEND.

This is separate from EnvConfigStore (which uses a FACTORY_ prefix for
application-level config). InfraEnvConfigStore is for infrastructure wiring
— the env vars that bricks and Dockerfiles use to select backends.
"""

from __future__ import annotations

import os
import time
from typing import Any

from factory.config.runtime.ports import ConfigHealth


class InfraEnvConfigStore:
    """Unprefixed env var adapter using pure dot→underscore convention."""

    def _key(self, key: str) -> str:
        """Convert dot-notation key to env var name.

        neo4j.uri → NEO4J_URI
        storage.doc.backend → STORAGE_DOC_BACKEND
        """
        return key.upper().replace(".", "_")

    def get(self, key: str, default: Any = None) -> Any:
        return os.environ.get(self._key(key), default)

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        value = self.get(key)
        if value is None:
            return default
        try:
            if value_type is bool:
                return str(value).lower() in ("true", "1", "yes", "on")
            return value_type(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        os.environ[self._key(key)] = str(value)
        return True

    def delete(self, key: str) -> bool:
        env_key = self._key(key)
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._key(key) in os.environ

    def keys(self, prefix: str = "") -> list[str]:
        """List keys — best-effort reverse mapping from env vars."""
        target = self._key(prefix) if prefix else ""
        result = []
        for env_key in os.environ:
            if env_key.isupper() and (not target or env_key.startswith(target)):
                result.append(env_key.lower().replace("_", "."))
        return result

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        return {key: self.get(key) for key in self.keys(prefix)}

    def health_check(self) -> ConfigHealth:
        start = time.time()
        latency = (time.time() - start) * 1000
        return ConfigHealth(
            healthy=True, backend="infra_env", latency_ms=latency,
            details={"type": "unprefixed_env"},
        )
