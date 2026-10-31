"""Games session explorer component.

Split out of :mod:`views.py` to keep each module under
the 200 LOC repo cap. The exported ``_game_sessions``
builder is consumed by the ``games_get_views`` tool
registered in :mod:`views`.
"""

from __future__ import annotations

from typing import Any


def _game_sessions() -> dict[str, Any]:
    """Active and finished game sessions as a calmer session explorer."""
    return {
        "id": "games-sessions",
        "type": "item_list",
        "props": {
            "data_tool": "games_get_dashboard_summary",
            "data_path": "$.games",
            "item_key": "game_id",
            "empty_icon": "puzzle-piece",
            "empty_message": "No game sessions yet.",
            "header": {
                "icon": "puzzle-piece",
                "stats_tool": "games_get_dashboard_summary",
                "stats_map": {
                    "games": "$.overview.games",
                    "active": "$.overview.active",
                    "activity": "$.overview.activity",
                },
            },
            "filters": {
                "field": "status",
                "values": ["active", "finished", "draw", "waiting"],
                "colors": {
                    "active": "emerald",
                    "finished": "gray",
                    "draw": "yellow",
                    "waiting": "blue",
                },
                "show_counts": False,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.status",
                    "states": {
                        "active": "emerald",
                        "finished": "gray",
                        "draw": "yellow",
                        "waiting": "blue",
                    },
                },
                "title": "$.game_id",
                "subtitle": "$.game_type",
                "badge": {
                    "field": "status",
                    "color_map": {
                        "active": "emerald",
                        "finished": "gray",
                        "draw": "yellow",
                        "waiting": "blue",
                    },
                    "suffix": "",
                },
                "value": {
                    "path": "$.move_count",
                    "format": "number",
                    "suffix": " moves",
                },
            },
            "detail": {
                "metadata": [
                    {"label": "Session", "path": "$.game_id",
                     "render_as": "copy_id", "zone": "identity"},
                    {"label": "Mode", "path": "$.game_type",
                     "render_as": "pills", "zone": "identity"},
                    {"label": "Status", "path": "$.status",
                     "zone": "identity"},
                    {"label": "Moves", "path": "$.move_count",
                     "zone": "identity"},
                    {"label": "Current Player",
                     "path": "$.current_player", "zone": "config"},
                    {"label": "Players", "path": "$.players",
                     "render_as": "popover", "zone": "config"},
                    {"label": "Winner", "path": "$.winner",
                     "zone": "config"},
                    {"label": "Run", "path": "$.run_id",
                     "render_as": "copy_id", "zone": "identity"},
                    {"label": "Graph", "path": "$.graph_id",
                     "render_as": "copy_id", "zone": "identity"},
                    {"label": "Target", "path": "$.target_app",
                     "render_as": "pills", "zone": "config"},
                    {"label": "Activity", "path": "$.activity_count",
                     "zone": "identity"},
                    {"label": "Last Activity", "path": "$.last_activity_label",
                     "zone": "config"},
                    {"label": "Config", "path": "$.config",
                     "render_as": "popover", "zone": "config"},
                    {"label": "Created", "path": "$.created_at",
                     "render_as": "relative_time",
                     "zone": "identity"},
                    {"label": "Updated", "path": "$.updated_at",
                     "render_as": "relative_time",
                     "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "state",
                        "label": "Board",
                        "tool": "games_get_state",
                        "args": {"game_id": "$.game_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "moves",
                        "label": "Moves",
                        "tool": "games_get_state",
                        "args": {"game_id": "$.game_id"},
                        "data_path": "$.move_history",
                        "render_as": "list",
                        "empty_message": "No moves yet.",
                    },
                    {
                        "id": "legal",
                        "label": "Legal Moves",
                        "tool": "games_legal_moves",
                        "args": {"game_id": "$.game_id"},
                        "data_path": "$.moves",
                        "render_as": "list",
                        "empty_message": "No legal moves available.",
                    },
                    {
                        "id": "evaluation",
                        "label": "Evaluation",
                        "tool": "games_evaluate",
                        "args": {"game_id": "$.game_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "activity",
                        "label": "Activity",
                        "tool": "games_get_game_activity",
                        "args": {"game_id": "$.game_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No recorded activity for this game yet.",
                    },
                    {
                        "id": "graph",
                        "label": "Graph",
                        "tool": "games_get_game_graph_context",
                        "args": {"game_id": "$.game_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No related graph entities found for this game yet.",
                    },
                ],
            },
        },
    }


__all__ = ["_game_sessions"]
