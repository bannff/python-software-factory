"""Typed deterministic MCP tools for Games."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, make_serializable

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, EvaluateOutput, GameIdInput,
    GamesListOutput, HealthOutput, LegalMovesOutput, ListGamesInput, StateOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import GamesRuntime


def register(mcp: Any, get_runtime: Callable[[], "GamesRuntime"]) -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        from ..runtime.runtime import GamesRuntime
        return {"name": "games", "version": "1.0.0",
                "game_types": GamesRuntime.available_game_types(),
                "backends": GamesRuntime.available_backends(),
                "features": ["game_sessions", "turn_based_play", "connect_four",
                "rl_environment", "legal_move_validation", "game_history"]}

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        return get_runtime().health_check()

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return {"type": "object", "properties": {"default_game_type": {
            "type": "string", "enum": ["connect_four"],
            "description": "Default game type for new sessions"}, "store_backend": {
            "type": "string", "enum": ["memory"],
            "description": "Session storage backend"}, "max_active_games": {
            "type": "integer", "description": "Max concurrent games"}}}

    @mcp.tool()
    @deterministic(input_model=GameIdInput, output_model=StateOutput)
    def games_get_state(game_id: str) -> ToolResult[StateOutput]:
        state = get_runtime().get_game(game_id)
        if state is None:
            return {"game_id": game_id, "game_type": "", "board": [],
                    "current_player": 0, "status": "", "move_history": [],
                    "players": {}, "config": {}, "created_at": "", "updated_at": "",
                    "move_count": 0, "error": f"Game {game_id} not found"}
        return make_serializable(state.to_dict())

    @mcp.tool()
    @deterministic(input_model=GameIdInput, output_model=LegalMovesOutput)
    def games_legal_moves(game_id: str) -> ToolResult[LegalMovesOutput]:
        moves = get_runtime().legal_moves(game_id)
        return make_serializable({"game_id": game_id, "moves": moves, "count": len(moves)})

    @mcp.tool()
    @deterministic(input_model=GameIdInput, output_model=EvaluateOutput)
    def games_evaluate(game_id: str) -> ToolResult[EvaluateOutput]:
        return make_serializable(get_runtime().evaluate(game_id))

    @mcp.tool()
    @deterministic(input_model=ListGamesInput, output_model=GamesListOutput)
    def games_list(status: str | None = None, limit: int = 20) -> ToolResult[GamesListOutput]:
        games = get_runtime().list_games(status=status, limit=limit)
        return make_serializable({"games": [game.to_dict() for game in games], "count": len(games)})
