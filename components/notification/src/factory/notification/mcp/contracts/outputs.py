"""Concrete Pydantic v2 egress DTOs for Notification MCP tools."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from .inputs import NotificationDTO


class CapabilitiesOutput(NotificationDTO):
    module: str
    version: str
    deterministic_tools: list[str]
    operational_tools: list[str]
    authoring: dict[str, str]


class HealthOutput(NotificationDTO):
    ok: bool
    backend: str
    channels_loaded: int
    templates_loaded: int


class RegistryItemOutput(NotificationDTO):
    id: str
    type: str | None = None
    name: str | None = None
    enabled: bool | None = None
    subject: str | None = None
    variables: list[str] | None = None
    config: dict[str, JsonValue] | None = None


class ChannelRegistryOutput(NotificationDTO):
    channels: list[RegistryItemOutput]
    count: int


class TemplateRegistryOutput(NotificationDTO):
    templates: list[RegistryItemOutput]
    count: int


class ConfigSchemaOutput(NotificationDTO):
    schema_version: int
    schemas: dict[str, JsonValue]


class DeliveryOutput(NotificationDTO):
    message_id: str | None = None
    status: Literal["queued", "sent", "delivered", "failed"] | None = None
    backend: str | None = None
    recipient: str | None = None
    channel_id: str | None = None
    timestamp: str | None = None
    error: str | None = None


class DeliveryStatusOutput(DeliveryOutput):
    found: bool


class SendNotificationOutput(DeliveryOutput):
    sent: bool


class DeliveriesOutput(NotificationDTO):
    deliveries: list[DeliveryOutput]
    count: int


class AuthoringStatusOutput(NotificationDTO):
    enabled: bool
    env_var: str


class AuthoringMutationOutput(NotificationDTO):
    ok: bool
    written: bool | None = None
    identifier: str | None = None
    deleted: bool | None = None
    error: str | None = None


__all__ = [name for name, value in globals().items() if isinstance(value, type)]
