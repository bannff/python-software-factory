"""Telemetry authoring - re-exports from authoring/ subpackage for backwards compatibility."""

from .authoring.manager import AuthoringManager
from .authoring.paths import AuthoringPaths
from .authoring.validation import (
    authoring_enabled,
    validate_settings,
    validate_metric_definitions,
    validate_exporter_config,
    AuthoringError,
)

__all__ = [
    "AuthoringManager",
    "AuthoringPaths",
    "authoring_enabled",
    "validate_settings",
    "validate_metric_definitions",
    "validate_exporter_config",
    "AuthoringError",
]
