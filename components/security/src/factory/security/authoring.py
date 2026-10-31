"""Authoring helpers for safely modifying security-module config via MCP.

These utilities restrict writes to the module's configured `config_dir`.

IMPORTANT: These capabilities are security-sensitive and must be explicitly enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Any

import yaml


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def authoring_enabled(settings: dict[str, Any] | None = None) -> bool:
    """Check if authoring tools are enabled."""
    if _truthy(os.getenv("SECURITY_ENABLE_AUTHORING_TOOLS")):
        return True
    if settings and isinstance(settings.get("authoring"), dict):
        return bool(settings["authoring"].get("enabled"))
    return False


@dataclass(frozen=True)
class AuthoringPaths:
    """Paths for authoring operations."""

    root: Path

    @property
    def rules_dir(self) -> Path:
        """Directory for security rules."""
        return self.root / "rules"

    @property
    def policies_dir(self) -> Path:
        """Directory for security policies."""
        return self.root / "policies"


class AuthoringError(ValueError):
    """Error raised when authoring operations fail."""

    pass


def _assert_within_root(root: Path, candidate: Path) -> None:
    """Ensure candidate path is within root."""
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as e:
        raise AuthoringError("Path escapes config root") from e


def _ensure_id(value: str) -> str:
    """Validate and return ID."""
    if not _ID_RE.match(value):
        raise AuthoringError("Invalid id; expected [a-zA-Z0-9][a-zA-Z0-9_-]{0,127}")
    return value


class AuthoringManager:
    """Manager for security authoring operations."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.paths = AuthoringPaths(root=self.config_dir)

    def get_status(self) -> dict[str, Any]:
        """Get authoring status."""
        return {
            "enabled": True,
            "config_dir": str(self.config_dir),
            "allowed_paths": [
                str(self.paths.rules_dir),
                str(self.paths.policies_dir),
            ],
        }

    def _rule_path(self, rule_id: str) -> Path:
        """Get path for a security rule."""
        rule_id = _ensure_id(rule_id)
        path = self.paths.rules_dir / f"{rule_id}.yaml"
        _assert_within_root(self.paths.root, path)
        return path

    def upsert_rule(
        self, *, id: str, config: dict[str, Any], dry_run: bool = False
    ) -> dict[str, Any]:
        """Create or update a security rule."""
        rule_id = _ensure_id(id)
        config = dict(config)
        config["id"] = rule_id

        path = self._rule_path(rule_id)
        if dry_run:
            return {"ok": True, "dry_run": True, "path": str(path)}

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        return {"ok": True, "dry_run": False, "path": str(path)}

    def delete_rule(self, *, id: str) -> dict[str, Any]:
        """Delete a security rule."""
        path = self._rule_path(id)
        if not path.exists():
            return {"ok": True, "deleted": False, "path": str(path)}
        path.unlink()
        return {"ok": True, "deleted": True, "path": str(path)}

    def list_rules(self) -> dict[str, Any]:
        """List all security rules."""
        rules_dir = self.paths.rules_dir
        if not rules_dir.exists():
            return {"rules": [], "count": 0}

        rules = []
        for path in sorted(rules_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text())
                rules.append({"id": path.stem, "path": str(path), "config": data})
            except Exception as e:
                rules.append({"id": path.stem, "path": str(path), "error": str(e)})

        return {"rules": rules, "count": len(rules)}
