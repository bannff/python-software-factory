"""MCP prompts for blueprint base."""

from __future__ import annotations

from typing import Callable

from typing import Any

from ..runtime.runtime import BlueprintRuntime


def register(mcp: Any, get_runtime: Callable[[], BlueprintRuntime]) -> None:
    """Register MCP prompts."""

    @mcp.prompt()
    def configure_service() -> str:
        """Guide for configuring a new service."""
        return """# Configure a New Service

To add a new service to the blueprint:

1. Add environment variable in `.env`:
   ```
   FACTORY_<SERVICE>_URL=<connection_string>
   ```

2. Update `core.py` InfrastructureSettings class

3. Update `runtime/runtime.py` to include the service

4. Test with `get_service_url("<service_name>")`
"""

    @mcp.prompt()
    def troubleshoot_connection() -> str:
        """Guide for troubleshooting service connections."""
        return """# Troubleshoot Service Connection

1. Check service health:
   ```
   health_check()
   ```

2. Verify URL is correct:
   ```
   get_service_url("<service_name>")
   ```

3. Common issues:
   - Service not running (check docker-compose)
   - Wrong port or host
   - Network/firewall blocking connection
   - Missing credentials
"""

    @mcp.prompt()
    def list_infrastructure() -> str:
        """Guide for viewing infrastructure status."""
        runtime = get_runtime()
        services = runtime.list_services()
        return f"""# Infrastructure Overview

Available services: {', '.join(services)}

Use these tools to inspect:
- `list_services()` - Get all service URLs
- `get_service_url("<name>")` - Get specific service
- `health_check()` - Check all service health

Resources:
- `blueprint://services` - Service list
- `blueprint://health` - Health status
"""
