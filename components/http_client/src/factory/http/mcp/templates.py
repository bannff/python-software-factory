"""Prompt templates for typed HTTP MCP workflows."""

PROMPT_TEMPLATES = {
    "make_request": {"title": "Make HTTP Request", "template": """# Making an HTTP Request

Method: {method}\nURL: {url}\nPurpose: {purpose}

Use `http_get` for GET, `http_post` for POST, `http_put` for PUT, and
`http_delete` for DELETE. Use `http_request(method=\"{method}\", url=...)` for
PATCH, HEAD, OPTIONS, and any other method.

Every result is a `ToolResult` envelope. Check `result.ok`; only then inspect
`result.data.status_code`, `result.data.headers`, `result.data.body`, and
`result.data.ok`. A 4xx or 5xx is a successful envelope with `data.ok=false`.
"""},
    "configure_client": {"title": "Configure HTTP Client", "template": """# Configuring HTTP Client

Goal: {goal}\nBackend: {backend}\nAuthentication: {auth_type}

Use `httpx` for general clients and `aiohttp` for async concurrency. Runtime
configuration provides retry, rate limiting, and authentication; MCP request
tools preserve flat headers and a strict numeric timeout.
"""},
    "debug_request": {"title": "Debug Failed Request", "template": """# Debugging an HTTP Request

URL: {url}\nObserved error: {error}\nStatus code: {status_code}

First distinguish a failed outer `ToolResult` (a safe transport failure) from a
successful envelope whose `data.ok` is false (an ordinary HTTP response). Use
`http_health_check` and `http_describe_config_schema` for diagnostics.
"""},
    "batch_requests": {"title": "Batch HTTP Operations", "template": """# Batch HTTP Operations

Goal: {goal}\nURLs:\n{urls}

Invoke the appropriate `http_*` request tool for each URL. Independently check
each outer ToolResult and, for successful envelopes, each `data.ok` value.
Apply rate limiting and timeouts appropriate to the target service.
"""},
}
