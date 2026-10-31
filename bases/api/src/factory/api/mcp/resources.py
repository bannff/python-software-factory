"""MCP resources for API base."""

from __future__ import annotations

import json
from typing import Callable

from typing import Any

from ..runtime.runtime import APIRuntime


def register(mcp: Any, get_runtime: Callable[[], APIRuntime]) -> None:
    """Register MCP resources."""

    @mcp.resource("api://routes")
    def list_all_routes() -> str:
        """List all registered API routes."""
        runtime = get_runtime()
        routes = runtime.list_routes()
        lines = ["# API Routes", ""]
        for route in routes:
            tags = f" [{', '.join(route.tags)}]" if route.tags else ""
            lines.append(f"- `{route.method}` **{route.path}**{tags}")
        return "\n".join(lines)

    @mcp.resource("api://openapi")
    def get_openapi_spec() -> str:
        """Get OpenAPI specification as JSON."""
        runtime = get_runtime()
        schema = runtime.get_openapi_schema()
        return json.dumps(schema, indent=2)

    @mcp.resource("api://health")
    def get_health_status() -> str:
        """Get API health status."""
        runtime = get_runtime()
        health = runtime.health_check()
        icon = "✅" if health.healthy else "❌"
        lines = [
            "# API Health",
            "",
            f"Status: {icon} {'Healthy' if health.healthy else 'Unhealthy'}",
            f"Adapter: {health.adapter}",
            f"Routes: {health.routes_count}",
        ]
        if health.error:
            lines.append(f"Error: {health.error}")
        return "\n".join(lines)

    @mcp.resource("api://docs")
    def get_docs() -> str:
        """API base documentation."""
        return """# API Base

API base provides a polymorphic HTTP API layer supporting REST and GraphQL.

## Features

- **REST API**: FastAPI-based REST endpoints
- **GraphQL API**: Strawberry-based GraphQL schema
- **OpenAPI**: Auto-generated OpenAPI 3.0 schema
- **Route Registration**: Dynamic route management

## Adapters

- `rest` (default) - FastAPI REST adapter
- `graphql` - Strawberry GraphQL adapter

## Usage

```python
from factory.api.runtime.runtime import get_runtime

runtime = get_runtime()
runtime.add_route("/users", "GET", get_users, tags=["users"])
```

## Configuration

Set adapter via environment or config:
- `FACTORY_API_ADAPTER=rest|graphql`
"""
