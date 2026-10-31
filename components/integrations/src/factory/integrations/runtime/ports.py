"""Protocol interfaces for integration connectors.

Ports define what capabilities connectors need, not how they're implemented.
Adapters plug in specific backends (REST, GraphQL, Webhook).
"""

from __future__ import annotations

from typing import Any, Protocol

from factory.integrations.runtime.email_models import (
    EmailIdempotencyConflict, EmailReceipt, SendEmailRequest,
)
from factory.mcp_utils.interface import ProtectedArtifactRef
from factory.integrations.runtime.models import ConnectorHealth, RequestResult


class ProtectedArtifactMaterializer(Protocol):
    """Materialize one exact owner-bound artifact through a trusted capability."""

    def materialize(
        self, artifact: ProtectedArtifactRef, principal_id: str, tenant_id: str,
    ) -> dict[str, Any]: ...


class EmailSender(Protocol):
    """Port for a provider-neutral, injected email sender."""

    def send(self, request: SendEmailRequest) -> EmailReceipt | EmailIdempotencyConflict:
        """Send the request or report a safe idempotency conflict."""
        ...


class Connector(Protocol):
    """Port: External service connector."""

    def connect(self) -> bool:
        """Establish connection. Returns True on success."""
        ...

    def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        ...

    def is_connected(self) -> bool:
        """Check if connector is currently connected."""
        ...

    def call(
        self,
        method: str,
        path: str = "",
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> RequestResult:
        """Make a request to the external service."""
        ...

    def health_check(self) -> ConnectorHealth:
        """Check connector health."""
        ...


class WebhookReceiver(Protocol):
    """Port: Incoming webhook handler."""

    def register(self, path: str, handler: Any) -> str:
        """Register a webhook handler. Returns registration ID."""
        ...

    def unregister(self, registration_id: str) -> bool:
        """Unregister a webhook handler. Returns True if found."""
        ...

    def list_registrations(self) -> list[dict[str, Any]]:
        """List all registered webhook handlers."""
        ...


class ProviderMessagingEgress(Protocol):
    """Port: vendor-neutral provider egress via the tokenless credential rail.

    Adapters delegate to auth's hidden ``auth.credentialed_egress`` tool as
    caller ``integrations``; they never see a token or touch a credential slot.
    """

    def send_email(self, *, provider_id: str, connection_ref: str, subject: str,
                   body: str, to: str, principal_id: str, tenant_id: str,
                   ) -> dict[str, Any]: ...


class MailboxReader(Protocol):
    """Port: read a mailbox through the same tokenless provider egress rail."""

    def list_messages(self, *, provider_id: str, connection_ref: str,
                      top: int, query: str, principal_id: str, tenant_id: str,
                      ) -> dict[str, Any]: ...
