"""Authoring helpers for safely modifying a Super Agent project via MCP."""

from .manager import AuthoringManager
from .paths import AuthoringPaths
from .policy import (
    AuthoringPolicy, authoring_policy, gated_tool, policy_for, settings_authoring_enabled,
)
from .roots import (
    AuthoringRoot,
    AuthoringRootUnavailable,
    config_root_for,
    ensure_root,
    packaged_skills_root,
    resolve_root,
)
from .validation import (
    validate_config,
    validate_tool_module,
    AuthoringError,
    ConfigKind,
)

__all__ = [
    "AuthoringManager",
    "AuthoringPaths",
    "AuthoringPolicy",
    "AuthoringRoot",
    "AuthoringRootUnavailable",
    "authoring_policy",
    "ensure_root",
    "gated_tool",
    "policy_for",
    "settings_authoring_enabled",
    "config_root_for",
    "packaged_skills_root",
    "resolve_root",
    "validate_config",
    "validate_tool_module",
    "AuthoringError",
    "ConfigKind",
]
