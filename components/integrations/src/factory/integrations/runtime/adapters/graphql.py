"""GraphQL connector adapter using gql.

Wraps the `gql` library to provide a GraphQL connector that
implements the same interface as RestConnector.
"""
from __future__ import annotations

import time
from typing import Any

from gql import Client, gql as parse_gql
from gql.transport.httpx import HTTPXTransport

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.models import (
    Connector,
    ConnectorConfig,
    ConnectorHealth,
    RequestResult,
)


class GraphQLConnector:
    """GraphQL connector backed by gql + httpx transport."""

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._client: Client | None = None
        self._status = ConnectorStatus.DISCONNECTED
        self._request_count = 0
        self._error_count = 0
        self._last_error: str | None = None

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    @property
    def status(self) -> ConnectorStatus:
        return self._status

    def connect(self) -> bool:
        try:
            transport = HTTPXTransport(
                url=self._config.base_url,
                headers=self._config.headers,
                timeout=self._config.timeout_seconds,
            )
            self._client = Client(transport=transport, fetch_schema_from_transport=False)
            self._status = ConnectorStatus.CONNECTED
            self._last_error = None
            return True
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False

    def disconnect(self) -> None:
        self._client = None
        self._status = ConnectorStatus.DISCONNECTED

    def is_connected(self) -> bool:
        return self._client is not None and self._status == ConnectorStatus.CONNECTED

    def call(
        self, method: str, path: str = "", params: dict[str, Any] | None = None,
        data: Any = None, headers: dict[str, str] | None = None,
    ) -> RequestResult:
        """Execute a GraphQL query/mutation.

        Convention: `data` should be a dict with keys:
          - "query": GraphQL query string (required)
          - "variables": dict of variables (optional)
        `method` and `path` are ignored for GraphQL.
        """
        if not self._client:
            return RequestResult(success=False, error="Not connected",
                                 connector_id=self._config.id)

        start = time.perf_counter()
        self._request_count += 1

        try:
            query_data = data if isinstance(data, dict) else {}
            query_str = query_data.get("query", "")
            variables = query_data.get("variables")
            document = parse_gql(query_str)
            result = self._client.execute(document, variable_values=variables)
            latency = (time.perf_counter() - start) * 1000
            return RequestResult(success=True, status_code=200, data=result,
                                 latency_ms=latency, connector_id=self._config.id)
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            latency = (time.perf_counter() - start) * 1000
            return RequestResult(success=False, error=str(e), latency_ms=latency,
                                 connector_id=self._config.id)

    def health_check(self) -> ConnectorHealth:
        healthy = self.is_connected()
        return ConnectorHealth(
            healthy=healthy, connector_count=1,
            connected_count=1 if healthy else 0,
            error_count=self._error_count,
            message=self._last_error or "OK",
        )

    def to_connector(self) -> Connector:
        return Connector(
            config=self._config, status=self._status,
            error_message=self._last_error,
            request_count=self._request_count,
            error_count=self._error_count,
        )
