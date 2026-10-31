"""Strict Pydantic v2 ingress DTOs for Notification MCP tools."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from factory.mcp_utils.runtime.bounded_json import is_bounded_json

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"


class NotificationDTO(BaseModel):
    """Reject unknown fields and coercion at the public boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(NotificationDTO):
    """Ingress for argument-free tools."""


class IdentifierInput(NotificationDTO):
    identifier: str = Field(pattern=ID_PATTERN)


class DeliveryStatusInput(NotificationDTO):
    message_id: str = Field(pattern=ID_PATTERN)


class ListDeliveriesInput(NotificationDTO):
    status: Literal["queued", "sent", "delivered", "failed"] | None = None
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class EnvelopeInput(NotificationDTO):
    """Legacy inert envelope, retained only as a strict compatibility field."""

    request_id: str | None = Field(default=None, max_length=256)
    timestamp: str | None = Field(default=None, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=256)
    principal_id: str | None = Field(default=None, max_length=256)
    session_id: str | None = Field(default=None, max_length=256)
    correlation_id: str | None = Field(default=None, max_length=256)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _bounded_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not is_bounded_json(value):
            raise ValueError("must be bounded JSON")
        return value


class SendNotificationInput(NotificationDTO):
    recipient: str = Field(min_length=1, max_length=2048)
    content: str | None = Field(default=None, max_length=65536)

    @field_validator("recipient")
    @classmethod
    def _nonblank_recipient(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value
    subject: str | None = Field(default=None, max_length=16384)
    template_id: str | None = Field(default=None, pattern=ID_PATTERN)
    channel_id: str | None = Field(default=None, pattern=ID_PATTERN)
    data: dict[str, JsonValue] | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    envelope: EnvelopeInput | None = None

    @field_validator("data")
    @classmethod
    def _bounded_json(cls, value: dict[str, JsonValue] | None) -> dict[str, JsonValue] | None:
        if value is not None and not is_bounded_json(value):
            raise ValueError("must be bounded JSON")
        return value


class UpsertChannelInput(NotificationDTO):
    channel_id: str = Field(pattern=ID_PATTERN)
    type: Literal["console", "slack", "email", "webhook", "sms"]
    config: dict[str, JsonValue]
    enabled: bool = True

    @field_validator("config")
    @classmethod
    def _bounded_config(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not is_bounded_json(value):
            raise ValueError("must be bounded JSON")
        return value


class UpsertTemplateInput(NotificationDTO):
    template_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=16384)
    body: str = Field(min_length=1, max_length=65536)
    subject: str | None = Field(default=None, max_length=16384)
    variables: list[str] | None = Field(default=None, max_length=64)


class ChannelIdentifierInput(NotificationDTO):
    channel_id: str = Field(pattern=ID_PATTERN)


class TemplateIdentifierInput(NotificationDTO):
    template_id: str = Field(pattern=ID_PATTERN)


__all__ = [name for name, value in globals().items() if isinstance(value, type)]
