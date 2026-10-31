"""File-based config adapter (YAML/JSON)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

from factory.config.runtime.ports import ConfigHealth


class FileConfigStore:
    """File-based implementation of ConfigStore port."""

    def __init__(self, path: str = "./config/settings.yaml") -> None:
        self._path = Path(path)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if not self._path.exists():
            self._data = {}
            return

        content = self._path.read_text()
        if self._path.suffix in (".yaml", ".yml"):
            self._data = yaml.safe_load(content) or {}
        elif self._path.suffix == ".json":
            self._data = json.loads(content)
        else:
            self._data = {}

    def _save(self) -> None:
        """Save configuration to file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.suffix in (".yaml", ".yml"):
            self._path.write_text(yaml.dump(self._data, default_flow_style=False))
        else:
            self._path.write_text(json.dumps(self._data, indent=2))

    def _get_nested(self, key: str) -> Any:
        """Get a nested value using dot notation."""
        parts = key.split(".")
        value = self._data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _set_nested(self, key: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        parts = key.split(".")
        data = self._data
        for part in parts[:-1]:
            if part not in data:
                data[part] = {}
            data = data[part]
        data[parts[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        value = self._get_nested(key)
        return value if value is not None else default

    def get_typed(self, key: str, value_type: type, default: Any = None) -> Any:
        """Get a configuration value with type coercion."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return value_type(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value."""
        self._set_nested(key, value)
        self._save()
        return True

    def delete(self, key: str) -> bool:
        """Delete a configuration key."""
        parts = key.split(".")
        data = self._data
        for part in parts[:-1]:
            if part not in data:
                return False
            data = data[part]
        if parts[-1] in data:
            del data[parts[-1]]
            self._save()
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if a configuration key exists."""
        return self._get_nested(key) is not None

    def keys(self, prefix: str = "") -> list[str]:
        """List configuration keys with optional prefix filter."""
        def _flatten(data: dict, parent: str = "") -> list[str]:
            keys = []
            for k, v in data.items():
                full_key = f"{parent}.{k}" if parent else k
                if isinstance(v, dict):
                    keys.extend(_flatten(v, full_key))
                else:
                    keys.append(full_key)
            return keys

        all_keys = _flatten(self._data)
        if prefix:
            return [k for k in all_keys if k.startswith(prefix)]
        return all_keys

    def get_all(self, prefix: str = "") -> dict[str, Any]:
        """Get all configuration values with optional prefix filter."""
        return {key: self.get(key) for key in self.keys(prefix)}

    def health_check(self) -> ConfigHealth:
        """Check file config health."""
        start = time.time()
        try:
            self._load()
            latency = (time.time() - start) * 1000
            return ConfigHealth(
                healthy=True, backend="file", latency_ms=latency,
                details={"path": str(self._path), "exists": self._path.exists()},
            )
        except Exception as e:
            return ConfigHealth(healthy=False, backend="file", message=str(e))
