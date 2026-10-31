"""Tenacity-backed HTTPX adapter.

Replaces hand-rolled retry loop with `tenacity` for robust,
configurable retry behavior with exponential backoff.
"""
from __future__ import annotations

import json
import time
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..ports import AuthConfig, HTTPHealth, HTTPResponse, RateLimitConfig, RetryConfig


class TenacityHTTPXClient:
    """HTTPX client with tenacity-powered retry."""

    def __init__(
        self, retry: RetryConfig | None = None, rate_limit: RateLimitConfig | None = None,
        auth: AuthConfig | None = None, base_url: str | None = None, **kwargs: Any,
    ) -> None:
        self._retry = retry or RetryConfig()
        self._rate_limit = rate_limit
        self._auth = auth or AuthConfig()
        self._base_url = base_url
        self._client: Any = None
        self._last_request_time: float = 0.0

    def _get_client(self) -> Any:
        if self._client is None:
            import httpx
            kw: dict[str, Any] = {}
            if self._base_url:
                kw["base_url"] = self._base_url
            self._client = httpx.Client(**kw)
        return self._client

    def _apply_auth(self, headers: dict[str, str]) -> dict[str, str]:
        h = headers.copy()
        if self._auth.auth_type == "bearer" and self._auth.token:
            h["Authorization"] = f"Bearer {self._auth.token}"
        elif self._auth.auth_type == "api_key" and self._auth.api_key_value:
            h[self._auth.api_key_header] = self._auth.api_key_value
        return h

    def _apply_rate_limit(self) -> None:
        if not self._rate_limit:
            return
        interval = 1.0 / self._rate_limit.requests_per_second
        elapsed = time.time() - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.time()

    def _prepare_body(self, body: Any, headers: dict[str, str]) -> tuple[bytes | None, dict[str, str]]:
        if body is None:
            return None, headers
        if isinstance(body, dict):
            headers.setdefault("Content-Type", "application/json")
            return json.dumps(body).encode(), headers
        if isinstance(body, str):
            return body.encode(), headers
        return body, headers

    def request(
        self, method: str, url: str, headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None, body: Any = None,
        timeout: float = 30.0, **kwargs: Any,
    ) -> HTTPResponse:
        client = self._get_client()
        hdrs = self._apply_auth(headers or {})
        content, hdrs = self._prepare_body(body, hdrs)
        cfg = self._retry

        class _RetryableStatus(Exception):
            def __init__(self, resp: Any, elapsed: float):
                self.resp = resp
                self.elapsed = elapsed

        @retry(
            stop=stop_after_attempt(cfg.max_retries + 1),
            wait=wait_exponential(multiplier=cfg.backoff_factor, min=cfg.backoff_factor),
            retry=retry_if_exception_type(_RetryableStatus),
            reraise=True,
        )
        def _do() -> HTTPResponse:
            self._apply_rate_limit()
            start = time.perf_counter()
            resp = client.request(method, url, headers=hdrs, params=params,
                                  content=content, timeout=timeout)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if (resp.status_code in cfg.retry_statuses
                    and method.upper() in cfg.retry_methods):
                raise _RetryableStatus(resp, elapsed_ms)
            return HTTPResponse(status_code=resp.status_code, headers=dict(resp.headers),
                                body=resp.content, elapsed_ms=elapsed_ms)

        try:
            return _do()
        except _RetryableStatus as e:
            return HTTPResponse(status_code=e.resp.status_code, headers=dict(e.resp.headers),
                                body=e.resp.content, elapsed_ms=e.elapsed)

    def get(self, url: str, **kw: Any) -> HTTPResponse:
        return self.request("GET", url, **kw)

    def post(self, url: str, body: Any = None, **kw: Any) -> HTTPResponse:
        return self.request("POST", url, body=body, **kw)

    def put(self, url: str, body: Any = None, **kw: Any) -> HTTPResponse:
        return self.request("PUT", url, body=body, **kw)

    def delete(self, url: str, **kw: Any) -> HTTPResponse:
        return self.request("DELETE", url, **kw)

    async def request_async(
        self, method: str, url: str, headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None, body: Any = None,
        timeout: float = 30.0, **kw: Any,
    ) -> HTTPResponse:
        import httpx
        hdrs = self._apply_auth(headers or {})
        content, hdrs = self._prepare_body(body, hdrs)
        async with httpx.AsyncClient(**({"base_url": self._base_url} if self._base_url else {})) as c:
            start = time.perf_counter()
            resp = await c.request(method, url, headers=hdrs, params=params,
                                   content=content, timeout=timeout)
            elapsed = (time.perf_counter() - start) * 1000
        return HTTPResponse(status_code=resp.status_code, headers=dict(resp.headers),
                            body=resp.content, elapsed_ms=elapsed)

    def health_check(self) -> HTTPHealth:
        start = time.perf_counter()
        try:
            self._get_client()
            return HTTPHealth(healthy=True, backend="tenacity_httpx",
                              latency_ms=(time.perf_counter() - start) * 1000)
        except Exception as e:
            return HTTPHealth(healthy=False, backend="tenacity_httpx",
                              latency_ms=(time.perf_counter() - start) * 1000, message=str(e))
