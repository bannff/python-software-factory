"""Safe, explicitly gated Permissions policy authoring helpers."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError
import yaml

from factory.permissions.authoring_safety import (
    SAFE_CODES, logical_policy_path, sanitized_validation_details, sanitized_validation_issue,
)
from factory.permissions.authoring_yaml import PolicyYamlError, load_bounded_policy, read_bounded_policy
from factory.permissions.runtime.models import PolicyDefinition

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "y", "on"}


def authoring_enabled(settings: dict[str, Any] | None = None) -> bool:
    if not _truthy(os.getenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS")):
        return False
    return not (settings and isinstance(settings.get("authoring"), dict)
                and settings["authoring"].get("enabled") is False)


@dataclass(frozen=True)
class AuthoringPaths:
    root: Path

    @property
    def policies_dir(self) -> Path:
        return self.root / "policies"


class AuthoringError(ValueError):
    """Stable authoring failure with bounded, sanitized details."""

    def __init__(self, code: str, details: list[dict[str, str]] | None = None):
        self.code = code if code in SAFE_CODES else "policy_validation_error"
        self.details = details or []
        super().__init__(self.code)


def _assert_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise AuthoringError("unsafe_policy_path") from exc


def _ensure_id(value: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise AuthoringError("unsafe_policy_path")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise AuthoringError("unsafe_policy_path")
    return value


class AuthoringManager:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.paths = AuthoringPaths(root=self.config_dir)

    def get_status(self) -> dict[str, Any]:
        return {"enabled": True, "config_dir": ".", "allowed_paths": ["policies"], "schema_versions": [1]}

    def _secure_policies_dir(self) -> Path:
        directory = self.paths.policies_dir
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise AuthoringError("unsafe_policy_path")
        _assert_within_root(self.paths.root, directory)
        return directory

    def _policy_path(self, policy_id: str) -> Path:
        policy_id = _ensure_id(policy_id)
        directory = self._secure_policies_dir()
        path = directory / f"{policy_id}.yaml"
        _assert_within_root(self.paths.root, path)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise AuthoringError("unsafe_policy_path")
        return path

    def _issue(self, path: object, error: Exception | str) -> dict[str, Any]:
        code = error if isinstance(error, str) else getattr(error, "code", "policy_validation_error")
        details = [] if isinstance(error, str) else sanitized_validation_details(error)
        if code not in SAFE_CODES:
            code = "policy_validation_error"
        return {"path": logical_policy_path(path), "error": code, "details": details[:8]}

    def validate_all_policies(self) -> dict[str, Any]:
        try:
            policies_dir = self._secure_policies_dir()
        except AuthoringError as exc:
            return {"ok": False, "count": 0, "errors": [self._issue("policies", exc)]}
        if not policies_dir.exists():
            return {"ok": True, "count": 0, "errors": []}
        files = sorted(policies_dir.glob("*.yaml"))
        errors: list[dict[str, Any]] = []
        for path in files:
            try:
                if path.is_symlink():
                    raise AuthoringError("unsafe_policy_path")
                _assert_within_root(self.paths.root, path)
                raw = read_bounded_policy(path)
                if not isinstance(raw, dict):
                    raise AuthoringError("policy_not_mapping")
                PolicyDefinition.model_validate(raw)
            except (AuthoringError, PolicyYamlError, ValidationError) as exc:
                errors.append(self._issue(path, exc))
            except OSError:
                errors.append(self._issue(path, "policy_read_error"))
        return {"ok": not errors, "count": len(files), "errors": errors}

    def upsert_policy_definition(self, *, id: str, yaml_or_object: Any, dry_run: bool = False) -> dict[str, Any]:
        policy_id = _ensure_id(id)
        try:
            parsed = load_bounded_policy(yaml_or_object)
        except PolicyYamlError as exc:
            raise AuthoringError(exc.code, sanitized_validation_details(exc)) from None
        if not isinstance(parsed, dict):
            raise AuthoringError("policy_not_mapping")
        parsed = dict(parsed)
        parsed["id"] = policy_id
        try:
            PolicyDefinition.model_validate(parsed)
        except ValidationError as exc:
            raise AuthoringError("policy_validation_error", sanitized_validation_details(exc)) from None
        path = self._policy_path(policy_id)
        if dry_run:
            return {"ok": True, "dry_run": True, "path": logical_policy_path(path)}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(parsed, sort_keys=False), encoding="utf-8")
        except OSError as exc:
            raise AuthoringError("policy_write_error") from exc
        return {"ok": True, "dry_run": False, "path": logical_policy_path(path)}

    def delete_policy_definition(self, *, id: str) -> dict[str, Any]:
        path = self._policy_path(id)
        if not path.exists():
            return {"ok": True, "deleted": False, "path": logical_policy_path(path)}
        try:
            path.unlink()
        except OSError as exc:
            raise AuthoringError("policy_delete_error") from exc
        return {"ok": True, "deleted": True, "path": logical_policy_path(path)}


__all__ = [
    "AuthoringError", "AuthoringManager", "authoring_enabled", "logical_policy_path",
    "sanitized_validation_details", "sanitized_validation_issue",
]
