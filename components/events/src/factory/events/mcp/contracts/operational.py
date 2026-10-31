"""DTOs for operational Events MCP tools."""
from __future__ import annotations

from .base import DTO, EventData, HistoryEntryData, JsonObject


class PublishInput(DTO):
    event_type: str
    payload: JsonObject
    source: str
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    attributes: JsonObject | None = None
    run_id_authoritative: bool = False


class PublishOutput(DTO):
    event_id: str
    status: str
    subscriptions_matched: int
    subscriptions_dispatched: int
    timestamp: str


class EventIdInput(DTO):
    event_id: str


class GetEventOutput(DTO):
    found: bool
    event: EventData | None = None
    error: str | None = None


class ListEventsInput(DTO):
    event_type: str | None = None
    source: str | None = None
    limit: int = 100


class ListEventsOutput(DTO):
    events: list[EventData]
    total: int


class ReplayInput(EventIdInput):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    attributes: JsonObject | None = None


class ReplayOutput(DTO):
    ok: bool
    new_event_id: str | None = None
    status: str | None = None
    subscriptions_matched: int | None = None
    error: str | None = None


class HistoryQueryInput(DTO):
    event_type: str | None = None
    source: str | None = None
    tenant_id: str | None = None
    payload_key: str | None = None
    payload_value: str | None = None
    limit: int = 100


class HistoryListInput(DTO):
    event_type: str | None = None
    source: str | None = None
    tenant_id: str | None = None
    limit: int = 100


class HistoryOutput(DTO):
    entries: list[HistoryEntryData]
    total: int


class PruneHistoryInput(DTO):
    older_than_iso: str | None = None


class PruneHistoryOutput(DTO):
    ok: bool
    deleted: int
    before_count: int
    after_count: int
    retention_days: int | None = None
    older_than_iso: str | None = None
