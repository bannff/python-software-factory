"""MCP prompts for integrations brick."""

from __future__ import annotations

from typing import Any

from factory.integrations.runtime.runtime import IntegrationsRuntime


def register(mcp: Any, runtime: IntegrationsRuntime) -> None:
    """Register MCP prompts."""

    @mcp.prompt()
    def configure_connector() -> str:
        """Guide for configuring a new connector."""
        return """# Configure a New Connector

## Step 1: Gather information
- **connector_id**: Unique identifier (e.g., "github", "stripe")
- **name**: Human-readable name
- **base_url**: API base URL
- **headers**: Authentication headers (if needed)

## Step 2: Register the connector
```python
runtime.register(
    connector_id="my-api",
    name="My External API",
    base_url="https://api.example.com/v1",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    timeout_seconds=30,
    retry_count=3,
)
```

## Step 3: Connect
```python
runtime.connect("my-api")
```

## Step 4: Verify
Use `integrations_get("my-api")` to check status.

## Common Headers
- Bearer token: `{"Authorization": "Bearer TOKEN"}`
- API key: `{"X-API-Key": "KEY"}`
- Basic auth: `{"Authorization": "Basic BASE64"}`
"""

    @mcp.prompt()
    def debug_connection() -> str:
        """Guide for debugging connection issues."""
        health = runtime.health_check()
        connectors = runtime.list_connectors()

        connector_status = "\n".join(
            f"- {c.config.id}: {c.status.value}"
            for c in connectors
        ) or "No connectors registered"

        return f"""# Debug Connection Issues

## Current State
- Total connectors: {health.connector_count}
- Connected: {health.connected_count}
- Errors: {health.error_count}

## Connector Status
{connector_status}

## Common Issues

### Connection refused
- Check base_url is correct
- Verify network connectivity
- Check firewall rules

### Authentication failed
- Verify API key/token is valid
- Check header format
- Ensure token hasn't expired

### Timeout errors
- Increase timeout_seconds
- Check if service is slow/overloaded
- Verify network latency

## Diagnostic Steps
1. `integrations_list()` - See all connectors
2. `integrations_get(id)` - Check specific connector
3. `health_check()` - Overall health
"""

    @mcp.prompt()
    def create_integration() -> str:
        """Guide for creating a complete integration."""
        return """# Create a Complete Integration

## Example: GitHub API Integration

### 1. Register
```python
runtime.register(
    connector_id="github",
    name="GitHub API",
    base_url="https://api.github.com",
    headers={
        "Authorization": "Bearer ghp_YOUR_TOKEN",
        "Accept": "application/vnd.github.v3+json",
    },
)
```

### 2. Connect
```python
runtime.connect("github")
```

### 3. Use
```python
# List repos
result = runtime.call("github", "GET", "/user/repos")

# Create issue
result = runtime.call(
    "github", "POST", "/repos/owner/repo/issues",
    data={"title": "Bug", "body": "Description"}
)
```

### 4. Cleanup
```python
runtime.disconnect("github")
```

## Best Practices
- Store credentials in environment variables
- Use appropriate timeouts for your use case
- Handle rate limiting gracefully
- Log errors for debugging
"""
