"""Chart and stream component builders for the Games dashboard."""

from __future__ import annotations

from typing import Any


def _status_mix_chart() -> dict[str, Any]:
    """Quick visual summary of game session states."""
    return {
        "id": "games-status-mix",
        "type": "chart",
        "props": {
            "title": "Session Status Mix",
            "data_tool": "games_get_dashboard_summary",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Create a game to populate the session overview.",
            "className": "mb-3",
        },
    }


def _activity_stream() -> dict[str, Any]:
    """Recent games activity shown as a compact operational lane."""
    return {
        "id": "games-activity-stream",
        "type": "item_list",
        "props": {
            "data_tool": "games_get_dashboard_summary",
            "data_path": "$.recent_activity",
            "item_key": "event_id",
            "empty_icon": "pulse",
            "empty_message": "No games activity recorded yet.",
            "header": {
                "icon": "pulse",
                "stats_tool": "games_get_dashboard_summary",
                "stats_map": {
                    "activity": "$.overview.activity",
                    "games": "$.overview.games",
                },
            },
            "filters": {
                "field": "event_type",
                "values": ["game.created", "game.move", "game.finished"],
                "colors": {
                    "game.created": "emerald",
                    "game.move": "blue",
                    "game.finished": "amber",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.label",
                "subtitle": "$.game_id",
                "badge": {"field": "event_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.age_label", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Game", "path": "$.game_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Graph", "path": "$.graph_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Target", "path": "$.target_app", "render_as": "pills", "zone": "config"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
            },
        },
    }


def _graph_context_stream() -> dict[str, Any]:
    """Related graph entities that anchor games activity into workflow/evals context."""
    return {
        "id": "games-graph-context",
        "type": "item_list",
        "props": {
            "data_tool": "games_get_dashboard_summary",
            "data_path": "$.related_graph_entities",
            "item_key": "entity_id",
            "empty_icon": "network",
            "empty_message": "No related graph entities yet.",
            "header": {
                "icon": "network",
                "stats_tool": "games_get_dashboard_summary",
                "stats_map": {
                    "entities": "$.overview.graph_entities",
                    "games": "$.overview.games",
                },
            },
            "filters": {
                "field": "entity_type",
                "values": ["GameSession", "GameMove", "WorkflowRun", "EvaluationRun", "Metric", "Finding"],
                "colors": {
                    "GameSession": "emerald",
                    "GameMove": "sky",
                    "WorkflowRun": "blue",
                    "EvaluationRun": "amber",
                    "Metric": "violet",
                    "Finding": "red",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.title",
                "subtitle": "$.subtitle",
                "badge": {"field": "entity_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.focus_game_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Game", "path": "$.focus_game_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }


__all__ = ["_status_mix_chart", "_activity_stream", "_graph_context_stream"]
