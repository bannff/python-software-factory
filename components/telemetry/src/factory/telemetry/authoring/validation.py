"""Validation utilities for telemetry authoring."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from factory.telemetry.runtime.config import ExporterConfig, MetricDefinition, Settings


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


class AuthoringError(ValueError):
    """Error raised during authoring operations."""
    pass


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def authoring_enabled(settings_raw: dict[str, Any] | None = None) -> bool:
    """Check if authoring tools are enabled."""
    if _truthy(os.getenv("TELEMETRY_ENABLE_AUTHORING_TOOLS")):
        return True
    if settings_raw and isinstance(settings_raw.get("authoring"), dict):
        return bool(settings_raw["authoring"].get("enabled"))
    return False


def assert_within_root(root: Path, candidate: Path) -> None:
    """Ensure candidate path is within root directory."""
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as e:
        raise AuthoringError("Path escapes config root") from e


def ensure_id(value: str) -> str:
    """Validate and return an ID string."""
    if not _ID_RE.match(value):
        raise AuthoringError("Invalid id; expected [a-zA-Z0-9][a-zA-Z0-9_-]{0,127}")
    return value


def validate_settings(content: dict[str, Any]) -> None:
    """Validate settings content."""
    Settings.model_validate(content)


def validate_metric_definitions(content: Any) -> None:
    """Validate metric definitions."""
    if not isinstance(content, list):
        raise AuthoringError("metrics YAML must be a list")
    for item in content:
        MetricDefinition.model_validate(item)


def validate_exporter_config(content: dict[str, Any]) -> None:
    """Validate exporter configuration."""
    ExporterConfig.model_validate(content)
