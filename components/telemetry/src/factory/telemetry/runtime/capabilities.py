"""Canonical Telemetry capability metadata shared by runtime and MCP."""
from __future__ import annotations

from pathlib import Path
from typing import Any

TOOL_CATEGORIES: dict[str, list[str]] = {
    "deterministic": [
        "get_capabilities", "health_check", "get_metric_registry",
        "get_exporter_registry", "get_metrics_summary", "describe_config_schema",
        "inject_context", "extract_context", "telemetry_get_views",
    ],
    "operational": [
        "flush_telemetry", "record_log", "record_llm_interaction",
        "record_agent_execution", "record_tool_invocation", "start_span", "end_span",
        "telemetry_ingest_batch", "telemetry_read_reference", "telemetry_materialize",
    ],
    "authoring": [
        "authoring_status", "list_configs", "read_config", "write_config",
        "write_metric_file", "delete_config",
    ],
}

RESOURCES = [
    "telemetry://schemas/settings", "telemetry://schemas/exporter",
    "telemetry://schemas/metric", "telemetry://docs", "telemetry://docs/overview",
    "telemetry://docs/otel", "telemetry://docs/metrics", "telemetry://docs/tracing",
    "telemetry://docs/when-to-use", "telemetry://metrics", "telemetry://exporters",
    "telemetry://summary", "telemetry://factory",
]
PROMPTS = ["configure_otel", "debug_telemetry", "create_metric"]


def capabilities_for(config_dir: Path) -> dict[str, Any]:
    """Return one capability payload for every mounted Telemetry surface."""
    return {
        "module": "telemetry-module",
        "version": "0.2.0",
        "deterministic_tools": TOOL_CATEGORIES["deterministic"],
        "recording_tools": [
            "record_log", "record_llm_interaction", "record_agent_execution",
            "record_tool_invocation", "start_span", "end_span",
        ],
        "context_tools": ["inject_context", "extract_context"],
        "admin_tools": ["flush_telemetry"],
        "provenance_tools": [
            "telemetry_ingest_batch", "telemetry_read_reference", "telemetry_materialize",
        ],
        "authoring": {
            "env_var": "TELEMETRY_ENABLE_AUTHORING_TOOLS",
            "config_dir": str(config_dir),
            "tools": TOOL_CATEGORIES["authoring"],
        },
        "tools": TOOL_CATEGORIES,
        "mcp_resources": RESOURCES,
        "mcp_prompts": PROMPTS,
    }
