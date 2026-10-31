"""Gmail-shaped injected-client adapter with no SDK, OAuth, or network dependency."""
from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from typing import Any, Protocol

from factory.integrations.runtime.email_models import (
    EmailReceipt, ProviderReceiptError, SendEmailRequest,
)

_GMAIL_RECEIPT_ID = re.compile(r"^[a-f0-9]{16,64}$")


class GmailSendRequest(Protocol):
    def execute(self) -> dict[str, Any]: ...


class GmailMessages(Protocol):
    def send(self, *, userId: str, body: dict[str, str]) -> GmailSendRequest: ...


class GmailUsers(Protocol):
    def messages(self) -> GmailMessages: ...


class GmailClient(Protocol):
    def users(self) -> GmailUsers: ...


class GmailEmailSender:
    """Map the neutral request to a Gmail-shaped injected client call."""

    def __init__(self, client: GmailClient) -> None:
        self._client = client

    def send(self, request: SendEmailRequest) -> EmailReceipt:
        message = EmailMessage()
        message["To"] = ", ".join(request.recipients)
        message["Subject"] = request.subject
        message.set_content(request.body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        response = self._client.users().messages().send(
            userId="me", body={"raw": raw},
        ).execute()
        message_id = response.get("id")
        if not isinstance(message_id, str) or not _GMAIL_RECEIPT_ID.fullmatch(message_id):
            raise ProviderReceiptError("invalid provider receipt")
        return EmailReceipt(
            status="sent", message_id=message_id,
            intent_digest=request.intent_digest(),
        )
