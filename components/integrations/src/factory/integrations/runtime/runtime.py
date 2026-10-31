"""Integrations runtime - orchestrates connector operations."""

from __future__ import annotations

from typing import Any, Union

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.adapters.rest import RestConnector
from factory.integrations.runtime.adapters.aws import AWSConnector
from factory.integrations.runtime.email_models import (
    EmailContent, EmailIdempotencyConflict, EmailReceipt, SendEmailRequest,
    SendProtectedEmailRequest,
)
from factory.integrations.runtime.email_registry import EmailConnectionRegistry
from factory.integrations.runtime.ports import EmailSender, ProtectedArtifactMaterializer
from factory.integrations.runtime.models import (
    Connector,
    ConnectorConfig,
    ConnectorHealth,
    RequestResult,
    Settings,
)

# Union type for all connector adapters
ConnectorAdapter = Union[RestConnector, AWSConnector]


class IntegrationsRuntime:
    """Main runtime for integration operations."""

    def __init__(
        self, settings: Settings | None = None,
        materializer: ProtectedArtifactMaterializer | None = None,
    ) -> None:
        self._settings = settings or Settings()
        if materializer is None:
            from factory.integrations.runtime.adapters.mcp_protected_artifacts import (
                MCPProtectedArtifactMaterializer,
            )
            materializer = MCPProtectedArtifactMaterializer()
        self._materializer = materializer
        self._connectors: dict[str, ConnectorAdapter] = {}
        self._email_connections = EmailConnectionRegistry()

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        return self._settings

    def register(
        self,
        connector_id: str,
        name: str,
        base_url: str,
        connector_type: str = "rest",
        headers: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
        retry_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Connector:
        """Register a new connector.
        
        Args:
            connector_id: Unique identifier for the connector
            name: Human-readable name
            base_url: Base URL (for REST) or "aws://<service>" (for AWS)
            connector_type: Type of connector ("rest", "aws", "graphql", "webhook")
            headers: HTTP headers (REST only)
            timeout_seconds: Request timeout
            retry_count: Number of retries
            metadata: Additional metadata (e.g., region, profile for AWS)
        """
        config = ConnectorConfig(
            id=connector_id,
            name=name,
            connector_type=connector_type,  # type: ignore
            base_url=base_url,
            headers=headers or {},
            timeout_seconds=timeout_seconds or self._settings.default_timeout_seconds,
            retry_count=retry_count or self._settings.default_retry_count,
            metadata=metadata or {},
        )

        # Create appropriate adapter based on type
        if connector_type == "aws":
            connector: ConnectorAdapter = AWSConnector(config)
        elif connector_type == "graphql":
            from factory.integrations.runtime.adapters.graphql import GraphQLConnector
            connector = GraphQLConnector(config)
        else:
            connector = RestConnector(config)
            
        self._connectors[connector_id] = connector
        return connector.to_connector()

    def unregister(self, connector_id: str) -> bool:
        """Unregister a connector."""
        connector = self._connectors.pop(connector_id, None)
        if connector:
            connector.disconnect()
            return True
        return False

    def connect(self, connector_id: str) -> bool:
        """Connect a registered connector."""
        connector = self._connectors.get(connector_id)
        if not connector:
            return False
        return connector.connect()

    def disconnect(self, connector_id: str) -> bool:
        """Disconnect a connector."""
        connector = self._connectors.get(connector_id)
        if not connector:
            return False
        connector.disconnect()
        return True

    def get(self, connector_id: str) -> Connector | None:
        """Get connector by ID."""
        connector = self._connectors.get(connector_id)
        return connector.to_connector() if connector else None

    def list_connectors(self) -> list[Connector]:
        """List all registered connectors."""
        return [c.to_connector() for c in self._connectors.values()]

    def call(
        self,
        connector_id: str,
        method: str,
        path: str = "",
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> RequestResult:
        """Make a request through a connector."""
        connector = self._connectors.get(connector_id)
        if not connector:
            return RequestResult(
                success=False,
                error=f"Connector '{connector_id}' not found",
                connector_id=connector_id,
            )
        return connector.call(method, path, params, data, headers)

    def register_email_connection(
        self, tenant_id: str, owner_id: str, connection_ref: str, sender: EmailSender,
    ) -> None:
        """Register an injected sender in one tenant and owner's opaque namespace."""
        self._email_connections.register(tenant_id, owner_id, connection_ref, sender)

    def send_email(
        self, tenant_id: str, owner_id: str, request: SendEmailRequest,
    ) -> EmailReceipt | EmailIdempotencyConflict | None:
        """Send only through a tenant and owner-resolved opaque reference."""
        return self._email_connections.send(tenant_id, owner_id, request)

    def send_protected_email(
        self, owner_id: str, tenant_id: str, request: SendProtectedEmailRequest,
    ) -> EmailReceipt | EmailIdempotencyConflict | None:
        """Materialize synchronously, validate plaintext, and send without retaining it."""
        descriptor = request.artifact.descriptor
        if descriptor.artifact_kind != "email" or descriptor.purpose != "email":
            raise ValueError("protected artifact unavailable")
        content = EmailContent.model_validate(
            self._materializer.materialize(request.artifact, owner_id, tenant_id),
        )
        private_request = SendEmailRequest(
            connection_ref=request.connection_ref,
            idempotency_key=request.idempotency_key,
            **content.model_dump(),
        )
        return self._email_connections.send(tenant_id, owner_id, private_request)

    def health_check(self) -> ConnectorHealth:
        """Check overall health of all connectors."""
        total = len(self._connectors)
        connected = sum(1 for c in self._connectors.values() if c.is_connected())
        errors = sum(
            1
            for c in self._connectors.values()
            if c.status == ConnectorStatus.ERROR
        )

        return ConnectorHealth(
            healthy=errors == 0,
            connector_count=total,
            connected_count=connected,
            error_count=errors,
            message=f"{connected}/{total} connectors connected",
        )
