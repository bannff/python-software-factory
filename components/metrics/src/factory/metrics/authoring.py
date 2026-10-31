"""Authoring manager for metrics YAML config management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class AuthoringError(Exception):
    """Raised when an authoring operation fails."""


def authoring_enabled() -> bool:
    """Check if authoring tools are enabled via env var."""
    return os.environ.get("METRICS_ENABLE_AUTHORING_TOOLS", "").lower() in (
        "1", "true", "yes",
    )


class AuthoringManager:
    """YAML-based config management for metric definitions."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.definitions_dir = config_dir / "definitions"
        self.definitions_dir.mkdir(parents=True, exist_ok=True)

    def list_definitions(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path in sorted(self.definitions_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text()) or {}
                data["_file"] = path.name
                results.append(data)
            except Exception as e:
                results.append({"_file": path.name, "_error": str(e)})
        return results

    def read_definition(self, metric_id: str) -> dict[str, Any]:
        path = self.definitions_dir / f"{metric_id}.yaml"
        if not path.exists():
            raise AuthoringError(f"Definition not found: {metric_id}")
        return yaml.safe_load(path.read_text()) or {}

    def write_definition(self, config: dict[str, Any]) -> dict[str, Any]:
        metric_id = config.get("id")
        if not metric_id:
            raise AuthoringError("Definition must have an 'id' field")
        path = self.definitions_dir / f"{metric_id}.yaml"
        path.write_text(yaml.safe_dump(config, default_flow_style=False))
        return {"ok": True, "id": metric_id, "path": str(path)}

    def delete_definition(self, metric_id: str) -> dict[str, Any]:
        path = self.definitions_dir / f"{metric_id}.yaml"
        if not path.exists():
            raise AuthoringError(f"Definition not found: {metric_id}")
        path.unlink()
        return {"ok": True, "id": metric_id, "deleted": True}
