"""MCP resources for blueprint base."""

from __future__ import annotations

from typing import Callable

from typing import Any

from ..runtime.runtime import BlueprintRuntime


def register(mcp: Any, get_runtime: Callable[[], BlueprintRuntime]) -> None:
    """Register MCP resources."""

    @mcp.resource("blueprint://services")
    def list_all_services() -> str:
        """List all configured infrastructure services."""
        runtime = get_runtime()
        urls = runtime.get_all_urls()
        lines = ["# Infrastructure Services", ""]
        for name, url in sorted(urls.items()):
            lines.append(f"- **{name}**: `{url}`")
        return "\n".join(lines)

    @mcp.resource("blueprint://services/{service_name}")
    def get_service_info(service_name: str) -> str:
        """Get information about a specific service."""
        runtime = get_runtime()
        url = runtime.get_service_url(service_name)
        if not url:
            return f"# Service Not Found: {service_name}"
        return f"# {service_name}\n\nURL: `{url}`"

    @mcp.resource("blueprint://health")
    def get_health_status() -> str:
        """Get health status of all services."""
        runtime = get_runtime()
        health = runtime.health_check()
        lines = ["# Service Health", ""]
        for name, status in sorted(health.items()):
            icon = "✅" if status.healthy else "❌"
            lines.append(f"- {icon} **{name}**: {status.url}")
        return "\n".join(lines)

    @mcp.resource("blueprint://docs")
    def get_docs() -> str:
        """Blueprint documentation."""
        return """# Blueprint Base

Blueprint provides infrastructure configuration and service discovery.

## Features

- **Service Discovery**: Find service URLs by name
- **Configuration**: Centralized infrastructure settings
- **Health Checks**: Monitor service availability

## Environment Variables

All settings use `FACTORY_` prefix:
- `FACTORY_POSTGRES_URL` - PostgreSQL connection
- `FACTORY_NEO4J_URL` - Neo4j bolt URL
- `FACTORY_REDIS_URL` - Redis connection
- `FACTORY_KEYCLOAK_URL` - Keycloak auth server
- `FACTORY_CHROMA_HOST/PORT` - ChromaDB vector store
"""
