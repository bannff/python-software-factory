"""Learning-progression component declaration for the Games dashboard."""
from __future__ import annotations

from typing import Any


def _learning_progress_stream() -> dict[str, Any]:
    """Per-workflow RL outcomes, ordered newest-first with score direction."""
    return {
        "id": "games-learning-progress",
        "type": "item_list",
        "props": {
            "data_tool": "games_get_dashboard_summary",
            "data_path": "$.learning_runs",
            "item_key": "run_id",
            "empty_icon": "chart-bar-square",
            "empty_message": (
                "No learning runs yet. Complete a workflow to see scores, rewards, "
                "and retained learnings here."
            ),
            "header": {
                "icon": "chart-bar",
                "stats_tool": "games_get_dashboard_summary",
                "stats_map": {
                    "runs": "$.overview.learning_runs",
                    "best F1": "$.overview.best_f1",
                    "reward": "$.overview.cumulative_reward",
                    "stored": "$.overview.learning_stored",
                },
            },
            "filters": {
                "field": "trend_direction",
                "values": ["improved", "regressed", "steady", "baseline"],
                "colors": {
                    "improved": "emerald", "regressed": "red",
                    "steady": "blue", "baseline": "gray",
                },
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.status",
                    "states": {"completed": "emerald", "active": "blue", "failed": "red"},
                },
                "title": "$.run_id",
                "subtitle": "$.target_app",
                "badge": {"field": "trend_direction", "color_map": "filters.colors"},
                "value": {"path": "$.f1", "format": "percent"},
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.f1_delta",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "sparkline": {
                    "data_path": "$.score_history", "color": "indigo", "height": 28,
                    "max_points": 12, "variant": "line",
                },
                "metadata": [
                    {"label": "Workflow", "path": "$.workflow_type", "zone": "config"},
                    {"label": "Target", "path": "$.target_app", "render_as": "pills", "zone": "config"},
                    {"label": "Domain", "path": "$.domain", "render_as": "pills", "zone": "config"},
                    {"label": "Precision", "path": "$.precision", "render_as": "score", "zone": "identity"},
                    {"label": "Recall", "path": "$.recall", "render_as": "score", "zone": "identity"},
                    {"label": "Reward", "path": "$.reward", "zone": "identity"},
                    {"label": "Reward state", "path": "$.reward_state", "zone": "identity"},
                    {"label": "Learning", "path": "$.learning_state", "zone": "identity"},
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Graph", "path": "$.graph_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Phase trace", "path": "$.phases", "render_as": "popover", "zone": "config"},
                    {"label": "Completed", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
            },
        },
    }


__all__ = ["_learning_progress_stream"]
