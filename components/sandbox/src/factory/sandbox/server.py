"""Native MCP v2 server interface exposing sandbox tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .runtime.runtime import SandboxRuntime
from .mcp import (
    authoring, deterministic, deterministic_extended, operational,
    operational_extended, register_prompts, register_resources,
)
from .mcp import cfn_tools, provision_tools
from .mcp.views import register as register_views


def _register_tools(registry: Any, runtime: SandboxRuntime, config_dir: Path | None) -> None:
    enable_authoring = authoring_enabled()
    manager = AuthoringManager(config_dir or Path.cwd()) if enable_authoring else None
    deterministic.register(registry, runtime)
    deterministic_extended.register(registry, runtime)
    operational.register(registry, runtime)
    operational_extended.register(registry, runtime)
    cfn_tools.register(registry, runtime)
    provision_tools.register(registry, runtime)
    authoring.register(registry, runtime, manager)
    register_views(registry, runtime)


def create_tool_catalog(
    runtime: SandboxRuntime | None = None, config_dir: Path | None = None,
) -> Any:
    """Create the transport-neutral Sandbox tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    if runtime is None:
        from .runtime.runtime import create_adapter
        runtime = SandboxRuntime(create_adapter())
    catalog = ToolCatalog("sandbox-module")
    _register_tools(catalog, runtime, config_dir)
    register_resources(catalog, runtime)
    register_prompts(catalog, runtime)
    return catalog


def create_mcp_server(
    runtime: SandboxRuntime | None = None, config_dir: Path | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, config_dir)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for sandbox brick."""
    from .core import SUPPORTED_ADAPTERS
    return {
        "name": "sandbox",
        "version": "0.1.0",
        "adapters": SUPPORTED_ADAPTERS,
        "backends": ["memory", "graph"],
        "features": [
            "environment_provisioning",
            "command_execution",
            "file_transfer",
            "session_management",
            "cfn_deployment",
            "manifest_provisioning",
        ],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for sandbox brick."""
    return {"healthy": True, "adapter": "mock"}


def describe_config_schema() -> dict[str, Any]:
    """Describe sandbox configuration schema."""
    return {
        "type": "object",
        "properties": {
            "instance_type": {"type": "string", "default": "t3.micro"},
            "timeout_seconds": {"type": "integer", "default": 3600},
            "auto_terminate": {"type": "boolean", "default": True},
            "store_backend": {
                "type": "string",
                "enum": ["memory", "graph"],
                "default": "memory",
            },
        },
    }
