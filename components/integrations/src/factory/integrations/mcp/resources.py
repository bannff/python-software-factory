"""MCP resources for integrations brick."""

from __future__ import annotations

from typing import Any

from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.integrations.mcp.docs import DOCS


def register(mcp: Any, runtime: IntegrationsRuntime) -> None:
    """Register MCP resources."""

    @mcp.resource("integrations://schemas/config")
    def schema_config() -> dict[str, Any]:
        """JSON schema for integrations configuration."""
        from factory.integrations.runtime.models import Settings

        return Settings.model_json_schema()

    @mcp.resource("integrations://schemas/connector")
    def schema_connector() -> dict[str, Any]:
        """JSON schema for connector object."""
        from factory.integrations.runtime.models import ConnectorConfig

        return ConnectorConfig.model_json_schema()

    @mcp.resource("integrations://docs")
    def docs_list() -> dict[str, Any]:
        """List available documentation."""
        return {"docs": list(DOCS.keys())}

    @mcp.resource("integrations://docs/{doc_name}")
    def docs_get(doc_name: str) -> str:
        """Get specific documentation."""
        return DOCS.get(doc_name, f"Documentation '{doc_name}' not found.")

    @mcp.resource("integrations://health")
    def health() -> dict[str, Any]:
        """Current health status."""
        return runtime.health_check().model_dump()

    @mcp.resource("integrations://connectors")
    def connectors() -> dict[str, Any]:
        """List all registered connectors."""
        return {
            "connectors": [c.model_dump() for c in runtime.list_connectors()],
            "count": len(runtime.list_connectors()),
        }
