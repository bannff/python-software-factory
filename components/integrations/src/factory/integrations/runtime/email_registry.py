"""Owner-isolated registry for injected email senders."""
from __future__ import annotations

from factory.integrations.runtime.email_models import EmailReceipt, SendEmailRequest
from factory.integrations.runtime.ports import EmailSender


class EmailConnectionRegistry:
    """Resolve opaque references only inside a tenant and owner namespace."""

    def __init__(self) -> None:
        self._connections: dict[tuple[str, str, str], EmailSender] = {}

    def register(
        self, tenant_id: str, owner_id: str, connection_ref: str, sender: EmailSender,
    ) -> None:
        self._connections[(tenant_id, owner_id, connection_ref)] = sender

    def send(
        self, tenant_id: str, owner_id: str, request: SendEmailRequest,
    ) -> EmailReceipt | None:
        """Return None for missing, foreign-owner, or foreign-tenant references."""
        sender = self._connections.get((tenant_id, owner_id, request.connection_ref))
        return sender.send(request) if sender else None
