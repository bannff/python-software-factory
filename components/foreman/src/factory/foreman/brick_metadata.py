"""BRICK.yaml metadata reads shared by dependency and sync workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def find_brick_yaml(name: str, workspace_root: Path) -> Path | None:
    """Locate a component or base BRICK.yaml by brick name."""
    for prefix in ("components", "bases"):
        candidate = workspace_root / prefix / name / "BRICK.yaml"
        if candidate.exists():
            return candidate
    return None


def read_brick_metadata(name: str, workspace_root: Path) -> dict[str, Any] | None:
    """Read one BRICK.yaml mapping, returning None when unavailable or invalid."""
    brick_yaml = find_brick_yaml(name, workspace_root)
    if brick_yaml is None:
        return None
    try:
        data = yaml.safe_load(brick_yaml.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def read_brick_pip_packages(name: str, workspace_root: Path) -> list[str] | None:
    """Read cached pip packages; return None when the field is absent."""
    data = read_brick_metadata(name, workspace_root)
    packages = data.get("pip_packages") if data is not None else None
    return list(packages) if isinstance(packages, list) else None


def read_brick_dependencies(name: str, workspace_root: Path) -> set[str]:
    """Read declared brick dependencies, ignoring malformed entries."""
    data = read_brick_metadata(name, workspace_root)
    dependencies = data.get("dependencies") if data is not None else None
    if not isinstance(dependencies, list):
        return set()
    return {dep.strip() for dep in dependencies if isinstance(dep, str) and dep.strip()}
