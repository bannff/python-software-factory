"""Shared strict JSON-safe DTOs for Events native MCP v2 boundaries."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    """Strict same-brick transport contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat empty input for contract tools."""


class EventData(DTO):
    id: str
    type: str
    payload: JsonObject
    source: str
    timestamp: str
    trace_id: str | None = None
    session_id: str | None = None
    principal_id: str | None = None


class HistoryEntryData(DTO):
    event_id: str
    event_type: str
    source: str
    timestamp: str
    tenant_id: str | None = None
    principal_id: str | None = None
    correlation_id: str | None = None
    payload: JsonObject | None = None
    metadata: JsonObject | None = None
