"""Abstract ports for http brick.

Ports define what capabilities the HTTP client needs, not how they're implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class HTTPHealth:
    """Health status for an HTTP client."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class HTTPResponse:
    """Response from an HTTP request."""
    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed_ms: float = 0.0

    @property
    def text(self) -> str:
        """Decode body as UTF-8 text."""
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse body as JSON."""
        import json
        return json.loads(self.body)

    @property
    def ok(self) -> bool:
        """Check if status code indicates success (2xx)."""
        return 200 <= self.status_code < 300


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_methods: tuple[str, ...] = ("GET", "HEAD", "OPTIONS", "PUT", "DELETE")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    burst_size: int = 20


@dataclass
class AuthConfig:
    """Configuration for authentication."""
    auth_type: str = "none"  # none, bearer, basic, api_key
    token: str | None = None
    username: str | None = None
    password: str | None = None
    api_key_header: str = "X-API-Key"
    api_key_value: str | None = None


class HTTPClient(Protocol):
    """Port: HTTP client for making requests."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        body: bytes | str | dict | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make an HTTP request."""
        ...

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a GET request."""
        ...

    def post(
        self,
        url: str,
        body: bytes | str | dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a POST request."""
        ...

    def put(
        self,
        url: str,
        body: bytes | str | dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a PUT request."""
        ...

    def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a DELETE request."""
        ...

    async def request_async(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        body: bytes | str | dict | None = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make an async HTTP request."""
        ...

    def health_check(self) -> HTTPHealth:
        """Check client health."""
        ...
