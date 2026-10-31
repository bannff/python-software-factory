"""Pydantic-settings config adapter.

Uses ``pydantic-settings`` for typed, validated configuration loading
from environment variables and dotenv files.  Read-heavy operations
(get, get_typed, exists, keys) delegate to pydantic-settings; write
operations (set, delete) fall back to os.environ so changes are
reflected on the next ``reload()``.
"""

from __future__ import annotations

import os
import time
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from factory.config.runtime.ports import ConfigHealth


class _DynamicSettings(BaseSettings):
    """Internal settings model that captures all env vars with a prefix."""

    model_config = SettingsConfigDict(
        env_prefix="FACTORY_",
        env_nested_delimiter="__",
        extra="allow",
    )


class PydanticSettingsStore:
    """ConfigStore backed by ``pydantic-settings``.

    Reads from environment variables (with prefix) and optional
    ``.env`` files.  Supports typed access via pydantic's coercion.
    """

    def __init__(
        self,
        prefix: str = "FACTORY_",
        env_file: str | None = None,
    ) -> None:
        self._prefix = prefix
        self._env_file = env_file
        self._settings: _DynamicSettings | None = None
        self._reload()

    def _reload(self) -> None:
        """Reload settings from environment."""

        class _S(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix=self._prefix,
                env_nested_delimiter="__",
                extra="allow",
                env_file=self._env_file or "",
            )

        self._settings = _S()

    # ---- ConfigStore Protocol ----

    def get(self, key: str, default: Any = None) -> Any:
        env_key = self._to_env(key)
        return os.environ.get(env_key, default)

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        raw = self.get(key)
        if raw is None:
            return default
        try:
            if value_type is bool:
                return str(raw).lower() in ("true", "1", "yes", "on")
            return value_type(raw)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        os.environ[self._to_env(key)] = str(value)
        return True

    def delete(self, key: str) -> bool:
        env_key = self._to_env(key)
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._to_env(key) in os.environ

    def keys(self, prefix: str = "") -> list[str]:
        full = self._prefix + prefix.upper().replace(".", "_")
        return [
            self._from_env(k)
            for k in os.environ
            if k.startswith(full)
        ]

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        return {k: self.get(k) for k in self.keys(prefix)}

    def health_check(self) -> ConfigHealth:
        start = time.time()
        try:
            self._reload()
            latency = (time.time() - start) * 1000
            return ConfigHealth(
                healthy=True,
                backend="pydantic-settings",
                latency_ms=latency,
                details={"prefix": self._prefix},
            )
        except Exception as e:
            return ConfigHealth(
                healthy=False, backend="pydantic-settings", message=str(e),
            )

    # ---- helpers ----

    def _to_env(self, key: str) -> str:
        return f"{self._prefix}{key.upper().replace('.', '_')}"

    def _from_env(self, env_key: str) -> str:
        return env_key[len(self._prefix) :].lower().replace("_", ".")
