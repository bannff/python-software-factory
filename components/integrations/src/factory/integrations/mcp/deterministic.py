"""Deterministic MCP tools - contract tools and read-only queries."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import deterministic

from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.integrations.mcp.contracts import (
    CallInput, ConnectorIdInput, ConnectorOutput, ConnectorsOutput, EmptyInput,
    ObjectOutput, RegisterInput, ViewsOutput,
)


def register(mcp: Any, runtime: IntegrationsRuntime) -> None:
    """Register deterministic tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ObjectOutput)
    def get_capabilities() -> dict[str, Any]:
        """Return machine-readable capabilities for integrations brick."""
        return {
            "name": "integrations",
            "version": "1.0.0",
            "features": [
                "rest_connector",
                "graphql_connector",
                "webhook_receiver",
                "connection_pooling",
                "retry_logic",
                "rate_limiting",
            ],
            "adapters": ["rest", "graphql", "webhook"],
            "mcp_contract": {
                "tools": ["get_capabilities", "health_check", "describe_config_schema"],
                "resources": True,
                "prompts": True,
            },
        }

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ObjectOutput)
    def health_check() -> dict[str, Any]:
        """Fast readiness probe for integrations brick."""
        health = runtime.health_check()
        return health.model_dump()

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ObjectOutput)
    def describe_config_schema() -> dict[str, Any]:
        """Return JSON schema for integrations configuration."""
        from factory.integrations.runtime.models import Settings

        return Settings.model_json_schema()

    @mcp.tool()
    @deterministic(input_model=ConnectorIdInput, output_model=ConnectorOutput)
    def integrations_get(connector_id: str) -> dict[str, Any]:
        """Get a specific connector by ID (``connector`` is null when unknown)."""
        connector = runtime.get(connector_id)
        return {"connector": connector.model_dump(mode="json") if connector else None}

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConnectorsOutput)
    def integrations_list() -> dict[str, Any]:
        """List all registered connectors."""
        return {"connectors": [c.model_dump(mode="json") for c in runtime.list_connectors()]}
