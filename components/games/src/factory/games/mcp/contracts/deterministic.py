"""DTOs for deterministic Games MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject, JsonOutput


class CapabilitiesOutput(DTO):
    name: str
    version: str
    game_types: list[str]
    backends: list[str]
    features: list[str]


class HealthOutput(DTO):
    healthy: bool
    backend: str
    active_games: int


class ConfigSchemaOutput(DTO):
    type: str
    properties: JsonObject


class GameIdInput(DTO):
    game_id: str


class ListGamesInput(DTO):
    status: str | None = None
    limit: int = 20


class GameStateOutput(DTO):
    game_id: str
    game_type: str
    board: list[list[int]]
    current_player: int
    status: str
    winner: int | None = None
    move_history: list[JsonObject]
    players: dict[str, str]
    config: JsonObject
    created_at: str
    updated_at: str
    move_count: int
    error: str | None = None


class StateOutput(GameStateOutput):
    pass


class LegalMovesOutput(DTO):
    game_id: str
    moves: list[JsonObject]
    count: int


class EvaluateOutput(JsonOutput):
    pass


class GamesListOutput(DTO):
    games: list[GameStateOutput]
    count: int
