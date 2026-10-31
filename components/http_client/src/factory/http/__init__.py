"""HTTP brick - HTTP client abstraction with retry, auth, rate limiting.

This brick provides a unified interface for HTTP requests across multiple
backends (httpx, aiohttp) with built-in retry logic, rate limiting, and auth.

Usage:
    from factory.http import get, post, HTTPResponse

    # Simple GET
    response = get("https://api.example.com/data")
    print(response.json())

    # POST with JSON body
    response = post("https://api.example.com/items", body={"name": "test"})
    print(response.status_code)

    # With auth
    from factory.http import get_runtime, AuthConfig
    runtime = get_runtime()
    client = runtime.get_client(auth=AuthConfig(auth_type="bearer", token="xxx"))
    response = client.get("https://api.example.com/protected")
"""

from .interface import (
    HTTPClient,
    HTTPResponse,
    HTTPHealth,
    RetryConfig,
    RateLimitConfig,
    AuthConfig,
    HTTPRuntime,
    get_runtime,
    reset_runtime,
)
from .core import (
    get,
    post,
    put,
    delete,
    request,
    get_async,
    post_async,
)

__all__ = [
    # Ports
    "HTTPClient",
    # Data classes
    "HTTPResponse",
    "HTTPHealth",
    "RetryConfig",
    "RateLimitConfig",
    "AuthConfig",
    # Runtime
    "HTTPRuntime",
    "get_runtime",
    "reset_runtime",
    # Convenience functions
    "get",
    "post",
    "put",
    "delete",
    "request",
    "get_async",
    "post_async",
]
