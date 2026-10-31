"""MCP Resource registration for Logger brick.

Resources expose static/queryable data:
- Schemas for configuration and log records
- Documentation on sinks and formatters
- Live log queries
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import LOGGER_DOCS

if TYPE_CHECKING:
    from factory.logger.runtime.runtime import LoggerRuntime


def register(mcp: Any, runtime: "LoggerRuntime") -> None:
    """Register all Logger resources with the MCP server."""

    # Schema resources
    @mcp.resource("logger://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for logger configuration."""
        return json.dumps(runtime.describe_config_schema(), indent=2)

    @mcp.resource("logger://schemas/record")
    def resource_record_schema() -> str:
        """Get the JSON schema for log records."""
        return json.dumps({
            "type": "object",
            "properties": {
                "timestamp": {"type": "string", "format": "date-time"},
                "level": {"type": "string", "enum": ["debug", "info", "warning", "error", "critical"]},
                "message": {"type": "string"},
                "logger": {"type": "string"},
                "source": {"type": "string", "nullable": True},
                "run_id": {"type": "string", "nullable": True},
                "tenant_id": {"type": "string", "nullable": True},
                "context": {"type": "object"},
            },
            "required": ["timestamp", "level", "message"],
        }, indent=2)

    # Documentation resources
    @mcp.resource("logger://docs")
    def resource_docs_list() -> str:
        """List available logger documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in LOGGER_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("logger://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get logger documentation by name."""
        if doc_name in LOGGER_DOCS:
            return LOGGER_DOCS[doc_name]["content"]
        available = list(LOGGER_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("logger://docs/when-to-use")
    def resource_when_to_use() -> str:
        """When to use logger vs telemetry."""
        return LOGGER_DOCS["when_to_use"]["content"]

    # Live data resources
    @mcp.resource("logger://status")
    def resource_status() -> str:
        """Get current logger status."""
        return json.dumps(runtime.health_check(), indent=2)

    @mcp.resource("logger://recent")
    def resource_recent() -> str:
        """Get recent log entries (last 20)."""
        entries = runtime.tail(n=20)
        return json.dumps({"entries": entries, "count": len(entries)}, indent=2)

    # Cross-reference to factory
    @mcp.resource("logger://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": [
                "foreman_info", "foreman_check",
                "foreman_guardian_check", "foreman_get_repo_guardrails",
            ],
        }, indent=2)
