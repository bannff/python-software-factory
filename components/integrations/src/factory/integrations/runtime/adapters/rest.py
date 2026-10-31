"""REST API connector adapter.

Delegates HTTP transport to the http brick (factory.http.interface).
Owns connector lifecycle, status tracking, and domain model mapping.
"""

from __future__ import annotations

import time
from typing import Any

from factory.http.interface import HTTPRuntime, HTTPClient, RetryConfig, HTTPResponse
from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.models import (
    Connector,
    ConnectorConfig,
    ConnectorHealth,
    RequestResult,
)


class RestConnector:
    """REST API connector — composes http brick for transport."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._client: HTTPClient | None = None
        self._status = ConnectorStatus.DISCONNECTED
        self._request_count = 0
        self._error_count = 0
        self._last_error: str | None = None

    @property
    def config(self) -> ConnectorConfig:
        """Get connector configuration."""
        return self._config

    @property
    def status(self) -> ConnectorStatus:
        """Get current status."""
        return self._status

    def connect(self) -> bool:
        """Create HTTP client via http brick."""
        try:
            http_runtime = HTTPRuntime()
            retry = RetryConfig(max_retries=self._config.retry_count)
            self._client = http_runtime.get_client(
                "httpx",
                retry=retry,
                base_url=self._config.base_url,
            )
            self._status = ConnectorStatus.CONNECTED
            self._last_error = None
            return True
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False

    def disconnect(self) -> None:
        """Release HTTP client."""
        self._client = None
        self._status = ConnectorStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None and self._status == ConnectorStatus.CONNECTED

    def call(
        self,
        method: str,
        path: str = "",
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> RequestResult:
        """Make HTTP request via http brick client."""
        if not self._client:
            return RequestResult(
                success=False,
                error="Not connected",
                connector_id=self._config.id,
            )

        start = time.perf_counter()
        self._request_count += 1

        try:
            # Merge config headers with per-request headers
            merged_headers = {**self._config.headers, **(headers or {})}

            # Build body from data
            body: bytes | str | dict | None = data

            resp: HTTPResponse = self._client.request(
                method=method.upper(),
                url=path,
                params=params,
                body=body,
                headers=merged_headers,
                timeout=float(self._config.timeout_seconds),
            )
            latency = (time.perf_counter() - start) * 1000

            # Map http brick response to integrations domain
            resp_data = None
            if resp.body:
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = resp.text

            return RequestResult(
                success=resp.ok,
                status_code=resp.status_code,
                data=resp_data,
                latency_ms=latency,
                connector_id=self._config.id,
            )
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            latency = (time.perf_counter() - start) * 1000
            return RequestResult(
                success=False,
                error=str(e),
                latency_ms=latency,
                connector_id=self._config.id,
            )

    def health_check(self) -> ConnectorHealth:
        """Check connector health."""
        start = time.perf_counter()
        healthy = self.is_connected()
        latency = (time.perf_counter() - start) * 1000

        return ConnectorHealth(
            healthy=healthy,
            connector_count=1,
            connected_count=1 if healthy else 0,
            error_count=self._error_count,
            latency_ms=latency,
            message=self._last_error or "OK",
        )

    def to_connector(self) -> Connector:
        """Convert to Connector model."""
        return Connector(
            config=self._config,
            status=self._status,
            error_message=self._last_error,
            request_count=self._request_count,
            error_count=self._error_count,
        )
