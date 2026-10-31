"""Documentation content for integrations brick."""

DOCS: dict[str, str] = {
    "overview": """# Integrations Brick

External service connectors with pluggable backends.

## Features
- REST API connector with retry logic
- GraphQL connector (planned)
- Webhook receiver (planned)
- Connection pooling
- Rate limiting support

## Connector Types
- **rest**: HTTP/REST API connector
- **graphql**: GraphQL API connector
- **webhook**: Incoming webhook handler

## Workflow
1. Register a connector with `integrations_register`
2. Connect with `integrations_connect`
3. Make requests with `integrations_call`
4. Disconnect when done with `integrations_disconnect`
""",
    "adapters": """# Integration Adapters

## REST Connector
Full-featured HTTP client:
- All HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Custom headers and query params
- JSON request/response handling
- Configurable timeout and retries
- Connection health monitoring

## GraphQL Connector (Planned)
GraphQL-specific features:
- Query and mutation support
- Variable substitution
- Schema introspection

## Webhook Receiver (Planned)
Incoming webhook handling:
- Path-based routing
- Signature verification
- Event queuing
""",
    "usage": """# Usage Examples

## Register and connect
```python
runtime.register(
    connector_id="github",
    name="GitHub API",
    base_url="https://api.github.com",
    headers={"Authorization": "Bearer TOKEN"},
)
runtime.connect("github")
```

## Make requests
```python
result = runtime.call(
    connector_id="github",
    method="GET",
    path="/user/repos",
    params={"per_page": 10},
)
```

## Cleanup
```python
runtime.disconnect("github")
runtime.unregister("github")
```
""",
}
