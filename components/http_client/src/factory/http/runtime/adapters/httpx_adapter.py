"""HTTPX adapter for HTTP brick.

Provides HTTP client using httpx library with retry, rate limiting, and auth.
"""

from __future__ import annotations

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


class HTTPXClient:
    """HTTPX-based HTTP client adapter."""

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
        self._base_url = base_url
        self._client: Any = None
        self._last_request_time: float = 0.0

    def _get_client(self) -> Any:
        """Lazy-load httpx client."""
        if self._client is None:
            try:
                import httpx
                kwargs = {}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = httpx.Client(**kwargs)
            except ImportError:
                raise ImportError("httpx required: pip install httpx")
        return self._client

    def _apply_auth(self, headers: dict[str, str]) -> dict[str, str]:
        """Apply authentication to headers."""
        headers = headers.copy()
        if self._auth.auth_type == "bearer" and self._auth.token:
            headers["Authorization"] = f"Bearer {self._auth.token}"
        elif self._auth.auth_type == "api_key" and self._auth.api_key_value:
            headers[self._auth.api_key_header] = self._auth.api_key_value
        return headers

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting by sleeping if needed."""
        if not self._rate_limit:
            return
        min_interval = 1.0 / self._rate_limit.requests_per_second
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

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
        """Make an HTTP request with retry logic."""
        client = self._get_client()
        headers = self._apply_auth(headers or {})

        # Prepare body
        content = None
        if body is not None:
            if isinstance(body, dict):
                content = json.dumps(body).encode()
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                content = body.encode()
            else:
                content = body

        last_error: Exception | None = None
        for attempt in range(self._retry.max_retries + 1):
            self._apply_rate_limit()
            try:
                start = time.perf_counter()
                response = client.request(
                    method, url, headers=headers, params=params, content=content, timeout=timeout
                )
                elapsed = (time.perf_counter() - start) * 1000

                if response.status_code in self._retry.retry_statuses:
                    if attempt < self._retry.max_retries and method.upper() in self._retry.retry_methods:
                        time.sleep(self._retry.backoff_factor * (2 ** attempt))
                        continue

                return HTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                    elapsed_ms=elapsed,
                )
            except Exception as e:
                last_error = e
                if attempt < self._retry.max_retries:
                    time.sleep(self._retry.backoff_factor * (2 ** attempt))
                    continue
                raise

        raise last_error or RuntimeError("Request failed")

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
        """Async HTTP request using httpx.AsyncClient."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required: pip install httpx")

        headers = self._apply_auth(headers or {})
        content = None
        if body is not None:
            if isinstance(body, dict):
                content = json.dumps(body).encode()
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                content = body.encode()
            else:
                content = body

        async with httpx.AsyncClient(**({"base_url": self._base_url} if self._base_url else {})) as client:
            start = time.perf_counter()
            response = await client.request(
                method, url, headers=headers, params=params, content=content, timeout=timeout
            )
            elapsed = (time.perf_counter() - start) * 1000

        return HTTPResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            elapsed_ms=elapsed,
        )

    def health_check(self) -> HTTPHealth:
        """Check httpx client health."""
        start = time.perf_counter()
        try:
            self._get_client()
            latency = (time.perf_counter() - start) * 1000
            return HTTPHealth(healthy=True, backend="httpx", latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return HTTPHealth(healthy=False, backend="httpx", latency_ms=latency, message=str(e))
