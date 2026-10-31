"""Authoring helpers for safely modifying workflow-module config via MCP.

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

from factory.workflow.runtime.models import WorkflowDefinition


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def authoring_enabled(settings: dict[str, Any] | None = None) -> bool:
    if _truthy(os.getenv("WORKFLOW_ENABLE_AUTHORING_TOOLS")):
        return True
    if settings and isinstance(settings.get("authoring"), dict):
        return bool(settings["authoring"].get("enabled"))
    return False


@dataclass(frozen=True)
class AuthoringPaths:
    root: Path

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"


class AuthoringError(ValueError):
    pass


def _assert_within_root(root: Path, candidate: Path) -> None:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as e:
        raise AuthoringError("Path escapes config root") from e


def _ensure_id(value: str) -> str:
    if not _ID_RE.match(value):
        raise AuthoringError("Invalid id; expected [a-zA-Z0-9][a-zA-Z0-9_-]{0,127}")
    return value


class AuthoringManager:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.paths = AuthoringPaths(root=self.config_dir)

    def get_status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "config_dir": str(self.config_dir),
            "allowed_paths": [str(self.paths.workflows_dir)],
            "schema_versions": ["v1"],
        }

    def _workflow_path(self, workflow_id: str) -> Path:
        workflow_id = _ensure_id(workflow_id)
        path = self.paths.workflows_dir / f"{workflow_id}.yaml"
        _assert_within_root(self.paths.root, path)
        return path

    def validate_all_workflows(self) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        workflows_dir = self.paths.workflows_dir
        if not workflows_dir.exists():
            return {"ok": True, "count": 0, "errors": []}

        files = sorted(workflows_dir.glob("*.yaml"))
        for path in files:
            try:
                raw = yaml.safe_load(path.read_text())
                if not isinstance(raw, dict):
                    raise AuthoringError("Workflow must parse to a mapping")
                WorkflowDefinition.model_validate(raw)
            except Exception as e:
                details = getattr(e, "errors", None)
                errors.append(
                    {
                        "path": str(path),
                        "error": str(e),
                        "details": details() if callable(details) else None,
                    }
                )

        return {"ok": len(errors) == 0, "count": len(files), "errors": errors}

    def upsert_workflow_definition(self, *, id: str, yaml_or_object: Any, dry_run: bool = False) -> dict[str, Any]:
        workflow_id = _ensure_id(id)
        if isinstance(yaml_or_object, str):
            parsed = yaml.safe_load(yaml_or_object)
        else:
            parsed = yaml_or_object

        if not isinstance(parsed, dict):
            raise AuthoringError("yaml_or_object must be YAML string or mapping")

        parsed = dict(parsed)
        parsed["id"] = workflow_id
        WorkflowDefinition.model_validate(parsed)

        path = self._workflow_path(workflow_id)
        if dry_run:
            return {"ok": True, "dry_run": True, "path": str(path)}

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(parsed, sort_keys=False))
        return {"ok": True, "dry_run": False, "path": str(path)}

    def delete_workflow_definition(self, *, id: str) -> dict[str, Any]:
        path = self._workflow_path(id)
        if not path.exists():
            return {"ok": True, "deleted": False, "path": str(path)}
        path.unlink()
        return {"ok": True, "deleted": True, "path": str(path)}
