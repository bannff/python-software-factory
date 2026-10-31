"""Core models for notification-module."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class NotificationEnvelope(BaseModel):
    """Standard context envelope for operations."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationRequest(BaseModel):
    """A request to send a notification."""
    recipient: str = Field(min_length=1)
    channel_id: str | None = None
    template_id: str | None = None
    content: str | None = None
    subject: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    priority: Literal["low", "normal", "high"] = "normal"


class DeliveryStatus(BaseModel):
    """Result of a send operation."""
    message_id: str
    status: Literal["queued", "sent", "delivered", "failed"]
    backend: str
    recipient: str = ""
    channel_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "status": self.status,
            "backend": self.backend,
            "recipient": self.recipient,
            "channel_id": self.channel_id,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }
