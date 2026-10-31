"""Native MCP v2 server interface exposing telemetry tools.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .runtime.runtime import TelemetryRuntime
from .mcp import deterministic, operational, authoring, resources, prompts
from .mcp.views import register as register_views

_RUNTIME: TelemetryRuntime | None = None


def get_runtime() -> TelemetryRuntime:
    """Return the process-wide Telemetry runtime and its single provider."""
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    config_dir = Path(os.environ.get("TELEMETRY_CONFIG_DIR", "./config/telemetry"))
    config_dir.mkdir(parents=True, exist_ok=True)

    # Self-heal: create default settings if missing
    settings_path = config_dir / "settings.yaml"
    if not settings_path.exists():
        import yaml
        settings_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "service": {"name": "factory", "version": "0.1.0"},
            "otel": {"enabled": True, "tracing_enabled": True, "metrics_enabled": True, "logging_enabled": True},
        }))

    # Self-heal: create console exporter if no exporters configured
    exporters_dir = config_dir / "exporters"
    exporters_dir.mkdir(parents=True, exist_ok=True)
    if not any(exporters_dir.glob("*.yaml")):
        import yaml
        (exporters_dir / "console.yaml").write_text(yaml.safe_dump({
            "id": "console",
            "kind": "console",
        }))

    runtime = TelemetryRuntime(config_dir)
    try:
        runtime.initialize()
    except Exception:
        required = (
            os.environ.get("MCP_SERVER_NAME") == "companion-x"
            or os.environ.get("TELEMETRY_REQUIRED", "").lower()
            in {"1", "true", "yes"}
        )
        if required:
            raise
        # Optional deployments retain the failed runtime so health exposes the
        # initialization error rather than manufacturing a healthy fallback.
    _RUNTIME = runtime
    return runtime


def _register_tools(registry: Any, runtime: TelemetryRuntime) -> None:
    global _RUNTIME
    _RUNTIME = runtime
    enabled = authoring_enabled(runtime.settings_raw)
    manager = AuthoringManager(runtime.config_dir) if enabled else None
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime, manager, enabled)
    register_views(registry)


def create_tool_catalog(runtime: TelemetryRuntime | None = None) -> Any:
    """Create the transport-neutral Telemetry tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("telemetry-module")
    _register_tools(catalog, active_runtime)
    resources.register(catalog, active_runtime)
    prompts.register(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: TelemetryRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for telemetry brick."""
    return {
        "name": "telemetry",
        "version": "1.1.0",
        "backends": ["otlp", "console", "storage"],
        "features": ["observability", "distributed_tracing", "metrics", "llm_token_tracking", "storage_persistence"],
    }


def health_check() -> dict[str, Any]:
    """Report the active provider/exporter health."""
    return get_runtime().health_check()


def describe_config_schema() -> dict[str, Any]:
    """Describe telemetry configuration schema."""
    return {
        "type": "object",
        "properties": {
            "exporter": {"type": "string", "enum": ["otlp", "console", "storage"]},
            "endpoint": {"type": "string", "description": "OTLP endpoint URL"},
            "storage_type": {"type": "string", "enum": ["document", "blob", "graph"], "description": "Storage backend type (for kind: storage)"},
        },
    }
