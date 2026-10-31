"""DTOs for Events dashboard and view MCP tools."""
from __future__ import annotations

from .base import DTO, HistoryEntryData, JsonObject


class HistoryEntryInput(DTO):
    event_id: str


class EventGraphContextInput(DTO):
    event_id: str
    limit: int = 12


class DashboardSummaryOutput(DTO):
    overview: JsonObject
    series: list[JsonObject]
    source_series: list[JsonObject]
    events: list[JsonObject]
    subscriptions: list[JsonObject]
    related_graph_entities: list[JsonObject]


class HistoryEntryOutput(DTO):
    found: bool
    event_id: str
    entry: HistoryEntryData | None = None


class EventGraphContextOutput(DTO):
    event_id: str
    entries: list[JsonObject]
    count: int


class ViewsOutput(DTO):
    views: list[JsonObject]
