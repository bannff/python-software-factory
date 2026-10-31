"""AWS service connector adapter using boto3.

Provides polymorphic access to AWS services through the Connector protocol.
"""

from __future__ import annotations

import time
from typing import Any

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.models import (
    Connector,
    ConnectorConfig,
    ConnectorHealth,
    RequestResult,
)


class AWSConnector:
    """AWS service connector using boto3.
    
    Supports multiple AWS services through a unified interface:
    - EC2: Instance management
    - SSM: Systems Manager commands
    - S3: Object storage
    - Bedrock: LLM inference
    - STS: Security Token Service
    """

    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._client: Any = None
        self._status = ConnectorStatus.DISCONNECTED
        self._request_count = 0
        self._error_count = 0
        self._last_error: str | None = None
        self._service_name = self._extract_service_name()

    def _extract_service_name(self) -> str:
        """Extract AWS service name from base_url or metadata."""
        # base_url format: "aws://<service>" or metadata.service
        if self._config.base_url.startswith("aws://"):
            return self._config.base_url.replace("aws://", "")
        return self._config.metadata.get("service", "sts")

    @property
    def config(self) -> ConnectorConfig:
        """Get connector configuration."""
        return self._config

    @property
    def status(self) -> ConnectorStatus:
        """Get current status."""
        return self._status

    def connect(self) -> bool:
        """Create boto3 client for the configured service."""
        try:
            import boto3

            region = self._config.metadata.get("region", "us-east-1")
            profile = self._config.metadata.get("profile")

            session_kwargs: dict[str, Any] = {"region_name": region}
            if profile:
                session_kwargs["profile_name"] = profile

            session = boto3.Session(**session_kwargs)
            self._client = session.client(self._service_name)
            self._status = ConnectorStatus.CONNECTED
            self._last_error = None
            return True
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False

    def disconnect(self) -> None:
        """Close boto3 client."""
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
        """Call AWS API method.
        
        Args:
            method: AWS API operation name (e.g., "describe_instances", "send_command")
            path: Unused for AWS (kept for protocol compatibility)
            params: Operation parameters as kwargs
            data: Additional data (merged with params)
            headers: Unused for AWS (kept for protocol compatibility)
        """
        if not self._client:
            return RequestResult(
                success=False,
                error="Not connected",
                connector_id=self._config.id,
            )

        start = time.perf_counter()
        self._request_count += 1

        try:
            # Merge params and data
            call_params = {**(params or {}), **(data or {})}
            
            # Get the method from the client
            operation = getattr(self._client, method, None)
            if not operation:
                return RequestResult(
                    success=False,
                    error=f"Unknown operation: {method}",
                    connector_id=self._config.id,
                )

            response = operation(**call_params)
            latency = (time.perf_counter() - start) * 1000

            # Remove ResponseMetadata for cleaner output
            if isinstance(response, dict):
                response.pop("ResponseMetadata", None)

            return RequestResult(
                success=True,
                status_code=200,
                data=response,
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
        """Check connector health by calling STS get_caller_identity."""
        start = time.perf_counter()
        
        if not self.is_connected():
            return ConnectorHealth(
                healthy=False,
                connector_count=1,
                connected_count=0,
                error_count=self._error_count,
                message="Not connected",
            )

        try:
            # Use STS to verify credentials
            import boto3
            sts = boto3.client("sts")
            sts.get_caller_identity()
            latency = (time.perf_counter() - start) * 1000
            
            return ConnectorHealth(
                healthy=True,
                connector_count=1,
                connected_count=1,
                error_count=self._error_count,
                latency_ms=latency,
                message="OK",
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ConnectorHealth(
                healthy=False,
                connector_count=1,
                connected_count=0,
                error_count=self._error_count,
                latency_ms=latency,
                message=str(e),
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
