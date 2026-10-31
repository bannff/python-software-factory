"""Strict MCP DTOs for artifact-reference-only email sending."""
from __future__ import annotations

from pydantic import Field

from factory.integrations.runtime.email_models import EmailReceipt, SendProtectedEmailRequest


class SendEmailInput(SendProtectedEmailRequest):
    """Flat wire contract containing an opaque protected artifact reference only."""


class SendEmailOutput(EmailReceipt):
    """Redacted receipt with an opaque provider projection only."""
    message_id: str = Field(min_length=1, max_length=256)
