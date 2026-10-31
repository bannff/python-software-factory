"""Native MCP v2 server interface for the Permissions brick."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .mcp import (
    register_authoring,
    register_deterministic,
    register_operational,
    register_prompts,
    register_resources,
)
from .runtime.runtime import PermissionsRuntime


def get_runtime() -> PermissionsRuntime:
    """Create a default PermissionsRuntime from environment / defaults."""
    config_dir = Path(os.environ.get("PERMISSIONS_CONFIG_DIR", "./config"))
    return PermissionsRuntime(config_dir)


def _normalize_authoring_settings(settings: object) -> dict[str, object] | None:
    """Preserve omitted-vs-explicit authoring config at the MCP edge."""
    if settings is None:
        return None
    if isinstance(settings, Mapping):
        return dict(settings)

    authoring = getattr(settings, "authoring", None)
    if authoring is None:
        return None
    fields_set = getattr(authoring, "model_fields_set", set())
    if "enabled" not in fields_set:
        return {}
    return {"authoring": {"enabled": authoring.enabled}}


def _register_tools(registry: Any, runtime: PermissionsRuntime) -> None:
    settings = _normalize_authoring_settings(getattr(runtime, "_settings", None))
    enable_authoring = authoring_enabled(settings)
    register_deterministic(registry, runtime, authoring_enabled=enable_authoring)
    register_operational(registry, runtime)
    if enable_authoring:
        register_authoring(registry, runtime, AuthoringManager(runtime._config_dir))


def create_tool_catalog(runtime: PermissionsRuntime | None = None) -> Any:
    """Create the transport-neutral Permissions tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("permissions-module")
    _register_tools(catalog, active_runtime)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: PermissionsRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for permissions brick."""
    return {
        "name": "permissions",
        "version": "1.0.0",
        "backends": ["yaml", "cedar"],
        "features": ["permissions", "access_control", "policy_evaluation", "cedar_policies"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for permissions brick."""
    return {"healthy": True, "policy_runtime": "yaml"}


def describe_config_schema() -> dict[str, Any]:
    """Describe permissions configuration schema."""
    return {
        "type": "object",
        "properties": {
            "policy_backend": {"type": "string", "enum": ["yaml", "cedar"]},
            "policy_dir": {"type": "string", "description": "Directory containing policy files"},
        },
    }
