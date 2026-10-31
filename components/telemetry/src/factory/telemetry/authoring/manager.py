"""CRUD operations manager for telemetry authoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import AuthoringPaths
from .validation import (
    AuthoringError,
    assert_within_root,
    ensure_id,
    validate_settings,
    validate_metric_definitions,
    validate_exporter_config,
)


class AuthoringManager:
    """CRUD operations scoped to a config directory."""

    def __init__(self, config_root: Path):
        self.paths = AuthoringPaths(root=config_root)

    def list_items(self, kind: str) -> list[dict[str, Any]]:
        """List items of a given kind."""
        if kind == "settings":
            return [{"kind": "settings", "path": str(self.paths.settings_file),
                     "exists": self.paths.settings_file.exists()}]
        
        base = self._get_base_dir(kind)
        if not base.exists():
            return []

        items: list[dict[str, Any]] = []
        for file_path in sorted(base.glob("*.yaml")):
            items.append({"kind": kind, "id": file_path.stem, "path": str(file_path)})
        return items

    def read_yaml(self, kind: str, item_id: str) -> dict[str, Any] | list[dict[str, Any]]:
        """Read a YAML config file."""
        if kind == "settings":
            path = self.paths.settings_file
            assert_within_root(self.paths.root, path)
            if not path.exists():
                return {}
            data = yaml.safe_load(path.read_text())
            return data if isinstance(data, dict) else {}

        item_id = ensure_id(item_id)
        base = self._get_base_dir(kind)
        path = base / f"{item_id}.yaml"

        assert_within_root(self.paths.root, path)
        if not path.exists():
            raise AuthoringError(f"Not found: {kind} '{item_id}'")
        data = yaml.safe_load(path.read_text())
        
        if kind == "metric":
            if not isinstance(data, list):
                raise AuthoringError("Metric config must parse to a list")
            return data
        if not isinstance(data, dict):
            raise AuthoringError("Exporter config must parse to a mapping")
        return data

    def write_yaml(self, kind: str, config: dict[str, Any]) -> dict[str, Any]:
        """Write a YAML config file."""
        if kind == "settings":
            if not isinstance(config, dict):
                raise AuthoringError("settings must be a mapping")
            validate_settings(config)
            path = self.paths.settings_file
            assert_within_root(self.paths.root, path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(config, sort_keys=False))
            return {"ok": True, "kind": "settings", "path": str(path)}

        if not isinstance(config, dict):
            raise AuthoringError("config must be a mapping")

        config_id = ensure_id(str(config.get("id", "")))
        if kind == "exporter":
            validate_exporter_config(config)
            base = self.paths.exporters_dir
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"{config_id}.yaml"
            assert_within_root(self.paths.root, path)
            path.write_text(yaml.safe_dump(config, sort_keys=False))
            return {"ok": True, "kind": "exporter", "id": config_id, "path": str(path)}

        raise AuthoringError("Use write_metric_file for metrics")

    def write_metric_file(self, file_id: str, definitions: list[dict[str, Any]]) -> dict[str, Any]:
        """Write a metric definitions file."""
        file_id = ensure_id(file_id)
        validate_metric_definitions(definitions)
        base = self.paths.metrics_dir
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{file_id}.yaml"
        assert_within_root(self.paths.root, path)
        path.write_text(yaml.safe_dump(definitions, sort_keys=False))
        return {"ok": True, "kind": "metric", "id": file_id, "path": str(path)}

    def delete_yaml(self, kind: str, item_id: str) -> dict[str, Any]:
        """Delete a YAML config file."""
        if kind == "settings":
            path = self.paths.settings_file
            assert_within_root(self.paths.root, path)
            if not path.exists():
                return {"ok": False, "error": "not_found"}
            path.unlink()
            return {"ok": True, "kind": "settings"}

        item_id = ensure_id(item_id)
        base = self._get_base_dir(kind)
        path = base / f"{item_id}.yaml"

        assert_within_root(self.paths.root, path)
        if not path.exists():
            return {"ok": False, "error": "not_found", "id": item_id}
        path.unlink()
        return {"ok": True, "kind": kind, "id": item_id}

    def _get_base_dir(self, kind: str) -> Path:
        """Get base directory for a config kind."""
        if kind == "metric":
            return self.paths.metrics_dir
        elif kind == "exporter":
            return self.paths.exporters_dir
        raise AuthoringError(f"Unknown kind: {kind}")
