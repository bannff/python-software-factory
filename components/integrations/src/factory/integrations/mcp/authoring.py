"""Authoring MCP tools - security-gated configuration changes."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import authoring as authoring_decorator

from factory.integrations.runtime.runtime import IntegrationsRuntime


def register(mcp: Any, runtime: IntegrationsRuntime) -> None:
    """Register authoring tools."""

    @mcp.tool()
    @authoring_decorator
    def integrations_register(
        connector_id: str,
        name: str,
        base_url: str,
        connector_type: str = "rest",
        headers: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        """Register a new connector.

        Args:
            connector_id: Unique identifier for the connector
            name: Human-readable name
            base_url: Base URL for the external service
            connector_type: Type of connector (rest, graphql, webhook)
            headers: Default headers for requests
            timeout_seconds: Request timeout
            retry_count: Number of retries on failure

        Returns:
            The registered connector configuration
        """
        connector = runtime.register(
            connector_id=connector_id,
            name=name,
            base_url=base_url,
            connector_type=connector_type,
            headers=headers,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
        )
        return connector.model_dump()

    @mcp.tool()
    @authoring_decorator
    def integrations_unregister(connector_id: str) -> dict[str, Any]:
        """Unregister a connector.

        Args:
            connector_id: ID of the connector to unregister

        Returns:
            Result with unregistration status
        """
        success = runtime.unregister(connector_id)
        return {"connector_id": connector_id, "unregistered": success}
