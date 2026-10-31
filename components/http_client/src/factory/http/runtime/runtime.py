"""HTTP runtime factory - selects and configures HTTP client adapters.

Usage:
    runtime = HTTPRuntime()
    client = runtime.get_client("httpx")  # or "aiohttp"
"""

from __future__ import annotations

import logging
from typing import Any

from .ports import HTTPClient, HTTPHealth, RetryConfig, RateLimitConfig, AuthConfig

logger = logging.getLogger(__name__)


class HTTPRuntime:
    """Factory for creating HTTP client adapters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._clients: dict[str, HTTPClient] = {}

    def get_client(
        self,
        backend: str = "httpx",
        retry: RetryConfig | None = None,
        rate_limit: RateLimitConfig | None = None,
        auth: AuthConfig | None = None,
        **kwargs: Any,
    ) -> HTTPClient:
        """Get or create an HTTP client adapter."""
        key = f"{backend}:{id(retry)}:{id(rate_limit)}:{id(auth)}"
        if key not in self._clients:
            self._clients[key] = self._create_client(
                backend, retry, rate_limit, auth, **kwargs
            )
        return self._clients[key]

    def _create_client(
        self,
        backend: str,
        retry: RetryConfig | None,
        rate_limit: RateLimitConfig | None,
        auth: AuthConfig | None,
        **kwargs: Any,
    ) -> HTTPClient:
        """Create an HTTP client adapter."""
        if backend == "httpx":
            from .adapters.httpx_adapter import HTTPXClient
            return HTTPXClient(retry=retry, rate_limit=rate_limit, auth=auth, **kwargs)
        elif backend == "aiohttp":
            from .adapters.aiohttp_adapter import AIOHTTPClient
            return AIOHTTPClient(retry=retry, rate_limit=rate_limit, auth=auth, **kwargs)
        elif backend == "tenacity_httpx":
            from .adapters.tenacity_httpx import TenacityHTTPXClient
            return TenacityHTTPXClient(retry=retry, rate_limit=rate_limit, auth=auth, **kwargs)
        raise ValueError(f"Unknown HTTP backend: {backend}. Available: {self.available_backends()}")

    def health_check(self) -> dict[str, HTTPHealth]:
        """Check health of all active clients."""
        return {name: client.health_check() for name, client in self._clients.items()}

    @staticmethod
    def available_backends() -> list[str]:
        """List available HTTP backends."""
        return ["httpx", "aiohttp", "tenacity_httpx"]


_runtime: HTTPRuntime | None = None


def get_runtime() -> HTTPRuntime:
    """Get the global HTTP runtime."""
    global _runtime
    if _runtime is None:
        _runtime = HTTPRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
