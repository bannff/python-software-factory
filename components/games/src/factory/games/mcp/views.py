"""Typed UIView definitions for the Games brick."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, make_serializable

from ..runtime.runtime import GamesRuntime
from .contracts.base import EmptyInput
from .contracts.views import (
    DashboardSummaryOutput, GameActivityInput, GameActivityOutput,
    GameGraphContextInput, GameGraphContextOutput, ViewsOutput,
)
from .dashboard_summary import build_dashboard_summary
from .views_learning import _learning_progress_stream
from .views_sessions import _game_sessions
from .views_streams import _activity_stream, _graph_context_stream, _status_mix_chart


def register(mcp: Any, runtime: GamesRuntime) -> None:
    """Register Games view definitions with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardSummaryOutput)
    def games_get_dashboard_summary() -> ToolResult[DashboardSummaryOutput]:
        return make_serializable(build_dashboard_summary(runtime))

    @mcp.tool()
    @deterministic(input_model=GameActivityInput, output_model=GameActivityOutput)
    def games_get_game_activity(game_id: str, limit: int = 20) -> ToolResult[GameActivityOutput]:
        from .dashboard_summary import list_recent_activity
        entries = list_recent_activity(limit=limit, game_id=game_id)
        return make_serializable({"game_id": game_id, "entries": entries, "count": len(entries)})

    @mcp.tool()
    @deterministic(input_model=GameGraphContextInput, output_model=GameGraphContextOutput)
    def games_get_game_graph_context(game_id: str, limit: int = 12) -> ToolResult[GameGraphContextOutput]:
        from .dashboard_summary import list_related_graph_entities
        entries = list_related_graph_entities(limit=limit, game_id=game_id)
        return make_serializable({"game_id": game_id, "entries": entries, "count": len(entries)})

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def games_get_views() -> ToolResult[ViewsOutput]:
        return {"views": [{"id": "games-play", "name": "Arena & Sessions",
            "brick": "games", "icon": "🎮", "layout": {"type": "flex", "direction": "column"},
            "components": [_learning_progress_stream(), _status_mix_chart(), _game_sessions(),
                           _activity_stream(), _graph_context_stream()],
            "metadata": {"description": "Playable sessions, move history, and RL training state",
                         "nav_label": "Games", "nav_order": 60}}]}
