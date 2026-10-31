"""MCP prompts for API base."""

from __future__ import annotations

from typing import Callable

from typing import Any

from ..runtime.runtime import APIRuntime


def register(mcp: Any, get_runtime: Callable[[], APIRuntime]) -> None:
    """Register MCP prompts."""

    @mcp.prompt()
    def create_route() -> str:
        """Guide for creating a new API route."""
        return """# Create a New API Route

To add a new route to the API:

1. Define your handler:
   ```python
   async def get_items(skip: int = 0, limit: int = 10):
       return {"items": [], "skip": skip, "limit": limit}
   ```

2. Register the route:
   ```python
   from factory.api.runtime.runtime import get_runtime
   
   runtime = get_runtime()
   runtime.add_route(
       path="/items",
       method="GET",
       handler=get_items,
       tags=["items"]
   )
   ```

3. Verify registration:
   ```python
   routes = runtime.list_routes()
   ```

4. Check OpenAPI schema at `/docs` or `/openapi.json`
"""

    @mcp.prompt()
    def switch_adapter() -> str:
        """Guide for switching between REST and GraphQL."""
        runtime = get_runtime()
        backends = runtime.available_backends()
        return f"""# Switch API Adapter

Available adapters: {', '.join(backends)}

## REST Adapter (default)
- FastAPI-based
- OpenAPI auto-generation
- Swagger UI at `/docs`

## GraphQL Adapter
- Strawberry-based
- GraphQL Playground at `/graphql`
- Schema introspection

## Switching

1. Set environment variable:
   ```bash
   export FACTORY_API_ADAPTER=graphql
   ```

2. Or configure in code:
   ```python
   from factory.api.runtime.runtime import APIRuntime
   from factory.api.runtime.adapters.graphql import GraphQLAdapter
   
   runtime = APIRuntime(adapter=GraphQLAdapter())
   ```

Note: Routes registered with REST adapter need to be re-registered
as GraphQL resolvers when switching.
"""

    @mcp.prompt()
    def debug_api() -> str:
        """Guide for debugging API issues."""
        return """# Debug API Issues

## Common Issues

### Route Not Found (404)
1. Check route is registered: `list_routes()`
2. Verify path matches exactly
3. Check HTTP method is correct

### Validation Error (422)
1. Check request body matches schema
2. Verify query parameters
3. Review OpenAPI schema at `/docs`

### Internal Error (500)
1. Check handler function for exceptions
2. Review logs for stack trace
3. Verify dependencies are available

## Diagnostic Tools

```python
# Check health
health_check()

# List routes
list_routes()

# Get OpenAPI schema
get_openapi_schema()
```

## Resources

- `api://routes` - All registered routes
- `api://health` - Health status
- `api://openapi` - OpenAPI specification
"""
