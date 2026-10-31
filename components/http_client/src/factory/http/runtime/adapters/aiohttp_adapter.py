"""AIOHTTP adapter for HTTP brick.

Provides async-first HTTP client using aiohttp library.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from ..ports import (
    HTTPResponse,
    HTTPHealth,
    RetryConfig,
    RateLimitConfig,
    AuthConfig,
)


class AIOHTTPClient:
    """AIOHTTP-based HTTP client adapter."""

    def __init__(
        self,
        retry: RetryConfig | None = None,
        rate_limit: RateLimitConfig | None = None,
        auth: AuthConfig | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._retry = retry or RetryConfig()
        self._rate_limit = rate_limit
        self._auth = auth or AuthConfig()
        self._base_url = base_url or ""

    def _apply_auth(self, headers: dict[str, str]) -> dict[str, str]:
        """Apply authentication to headers."""
        headers = headers.copy()
        if self._auth.auth_type == "bearer" and self._auth.token:
            headers["Authorization"] = f"Bearer {self._auth.token}"
        elif self._auth.auth_type == "api_key" and self._auth.api_key_value:
            headers[self._auth.api_key_header] = self._auth.api_key_value
        return headers

    def _build_url(self, url: str) -> str:
        """Build full URL with base URL."""
        if url.startswith(("http://", "https://")):
            return url
        return f"{self._base_url.rstrip('/')}/{url.lstrip('/')}"

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
        """Sync request (runs async in thread)."""
        return asyncio.get_event_loop().run_until_complete(
            self.request_async(method, url, headers, params, body, timeout, **kwargs)
        )

    def get(self, url: str, **kwargs: Any) -> HTTPResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, body: Any = None, **kwargs: Any) -> HTTPResponse:
        return self.request("POST", url, body=body, **kwargs)

    def put(self, url: str, body: Any = None, **kwargs: Any) -> HTTPResponse:
        return self.request("PUT", url, body=body, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> HTTPResponse:
        return self.request("DELETE", url, **kwargs)

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
        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp required: pip install aiohttp")

        headers = self._apply_auth(headers or {})
        full_url = self._build_url(url)

        data = None
        if body is not None:
            if isinstance(body, dict):
                data = json.dumps(body)
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                data = body
            else:
                data = body

        timeout_obj = aiohttp.ClientTimeout(total=timeout)

        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            start = time.perf_counter()
            async with session.request(
                method, full_url, headers=headers, params=params, data=data
            ) as response:
                content = await response.read()
                elapsed = (time.perf_counter() - start) * 1000

                return HTTPResponse(
                    status_code=response.status,
                    headers={k: v for k, v in response.headers.items()},
                    body=content,
                    elapsed_ms=elapsed,
                )

    def health_check(self) -> HTTPHealth:
        """Check aiohttp availability."""
        start = time.perf_counter()
        try:
            import aiohttp
            latency = (time.perf_counter() - start) * 1000
            return HTTPHealth(healthy=True, backend="aiohttp", latency_ms=latency)
        except ImportError as e:
            latency = (time.perf_counter() - start) * 1000
            return HTTPHealth(healthy=False, backend="aiohttp", latency_ms=latency, message=str(e))
