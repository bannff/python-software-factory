"""DTOs for Games dashboard MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject
from .deterministic import GameIdInput


class DashboardSummaryOutput(DTO):
    overview: JsonObject
    series: list[JsonObject]
    learning_runs: list[JsonObject]
    games: list[JsonObject]
    recent_activity: list[JsonObject]
    related_graph_entities: list[JsonObject]


class GameActivityInput(GameIdInput):
    limit: int = 20


class GameActivityOutput(DTO):
    game_id: str
    entries: list[JsonObject]
    count: int


class GameGraphContextInput(GameIdInput):
    limit: int = 12


class GameGraphContextOutput(GameActivityOutput):
    pass


class ViewsOutput(DTO):
    views: list[JsonObject]
