"""Documentation content for HTTP brick MCP resources."""

HTTP_DOCS = {
    "overview": {
        "title": "HTTP Brick Overview",
        "content": """# HTTP Brick

The HTTP brick offers provider-neutral httpx and aiohttp request clients with
retry, rate limiting, authentication, and request timeouts.

## Typed MCP contract

Every HTTP tool returns a v1 `ToolResult` envelope. Check `ok` first; on
success, consume the typed payload only from `data`. HTTP 4xx and 5xx responses
are successful envelopes whose `data.ok` is false. Transport/runtime failures
are failed envelopes with the safe `http_transport_error` code.

## Tools

- `http_get_capabilities`, `http_health_check`, `http_describe_config_schema`
- `http_list_backends`
- `http_get`, `http_post`, `http_request`, `http_put`, `http_delete`

Request inputs remain flat. `body` is an object, string, or null. For PATCH,
HEAD, OPTIONS, and other methods use `http_request(method=..., url=...)`.

## Response data

Successful request data is `{status_code, headers, body, elapsed_ms, ok}`.
The outer envelope is not the response data.
""",
    },
    "adapters": {
        "title": "HTTP Adapters Documentation",
        "content": """# HTTP Adapters

`httpx` is the default general-purpose client with HTTP/2 and connection
pooling. `aiohttp` is optimized for high-concurrency async clients.

Use the runtime API for configured clients. MCP callers use the nine `http_*`
tools and inspect `ToolResult.data` only after confirming the envelope is OK.
""",
    },
    "retry": {
        "title": "Retry Configuration",
        "content": """# Retry Configuration

`RetryConfig` controls retries, backoff, retry statuses, and retryable methods
for runtime clients. HTTP MCP request tools retain a per-request `timeout`
default of 30.0 seconds.
""",
    },
    "auth": {
        "title": "Authentication Configuration",
        "content": """# Authentication Configuration

Runtime clients support bearer, basic, and API-key authentication. Configure
credentials through the runtime API; MCP request tools accept explicit request
headers as flat string maps.
""",
    },
}
