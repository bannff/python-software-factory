"""DTOs for deterministic Events MCP tools."""
from __future__ import annotations

from .base import DTO, EventData, JsonObject


class QueryEventsInput(DTO):
    event_type: str | None = None
    source: str | None = None
    payload_key: str | None = None
    payload_value: str | None = None
    limit: int = 100


class CapabilitiesOutput(DTO):
    version: str
    authoring_enabled: bool
    config_dir: str
    features: JsonObject


class HealthOutput(DTO):
    status: str
    config_dir: str
    subscriptions_loaded: int | None = None
    history_retention_days: int | None = None
    error: str | None = None


class ConfigSchemaOutput(DTO):
    event_schema: JsonObject
    subscription_schema: JsonObject
    envelope_schema: JsonObject
    history_entry_schema: JsonObject
    history_retention: JsonObject
    learning_event_schemas: JsonObject


class SubscriptionRegistryOutput(DTO):
    subscriptions: list[JsonObject]
    total: int


class QueryEventsOutput(DTO):
    events: list[EventData]
    total: int
