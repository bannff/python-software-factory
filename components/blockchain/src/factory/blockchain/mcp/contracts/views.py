"""DTOs for Blockchain dashboard and view MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class DashboardSummaryOutput(DTO):
    overview: JsonObject
    series: list[JsonObject]
    transactions: list[JsonObject]
    bounties: list[JsonObject]
    recent_activity: list[JsonObject]
    related_graph_entities: list[JsonObject]


class ActivityInput(DTO):
    tx_id: str = ""
    bounty_id: str = ""
    wallet_id: str = ""
    limit: int = 20


class ActivityOutput(DTO):
    tx_id: str
    bounty_id: str
    wallet_id: str
    entries: list[JsonObject]
    count: int


class EntityGraphContextInput(DTO):
    entity_id: str
    limit: int = 12


class EntityGraphContextOutput(DTO):
    entity_id: str
    entries: list[JsonObject]
    count: int


class ViewsOutput(DTO):
    views: list[JsonObject]
