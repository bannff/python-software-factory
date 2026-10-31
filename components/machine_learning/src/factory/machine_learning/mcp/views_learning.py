"""Learning-loop UIView for the Machine Learning brick (secondary view).

Event-backed RL learning-run projection — chat-turn reward/memory
lifecycle, NOT model training. Moved out of ``views.py`` when the
primary ML Models view landed (bd:python-factory-zgg1x) so the tab
stops presenting RL projections as training runs; kept as views[1]
for the RL-visibility work (bd:python-factory-61yn).
"""

from __future__ import annotations

from typing import Any

from .views_observatory import header


def learning_view() -> dict[str, Any]:
    """Return the event-backed learning-runs UIView definition."""
    return {
        "id": "ml-learning-runs",
        "name": "Learning Runs",
        "brick": "machine_learning",
        "icon": "🧠",
        "layout": {"type": "flex", "direction": "column"},
        "components": [
            header("Reward, penalty, memory, convergence, events, and artifacts remain distinct."),
            _item_list(),
        ],
        "metadata": {
            "description": "Event-backed learning loop tracking",
            "nav_label": "Learning",
            "nav_order": 53,
        },
    }


def _item_list() -> dict[str, Any]:
    """Build the learning-run item_list component (top-level, no page wrapper)."""
    return {
        "id": "ml-learning-run-list",
        "type": "item_list",
        "props": {
            "data_tool": "ml_list_learning_runs",
            "data_path": "$.learning_runs",
            "refresh_ms": 5000,
            "item_snapshot_tool": "ml_get_learning_run",
            "item_snapshot_args": {"run_id": "$.run_id"},
            "snapshot_merge_path": "snapshot",
            "item_key": "workflow_run_id",
            "empty_icon": "cpu-chip",
            "empty_message": "No learning runs yet.",
            "header": {
                "icon": "cpu-chip",
                "stats_tool": "ml_get_learning_summary",
                "stats_map": {
                    "runs": "$.total_runs",
                    "rewarded": "$.rewarded_runs",
                    "stored": "$.memory_backed_runs",
                    "converged": "$.converged_runs",
                },
            },
            "filters": {
                "field": "stage",
                "values": ["running", "completed", "failed", "scored", "rewarded", "stored", "checked", "converged", "unknown"],
                "colors": {
                    "running": "blue",
                    "completed": "slate",
                    "failed": "red",
                    "scored": "amber",
                    "rewarded": "emerald",
                    "stored": "cyan",
                    "checked": "blue",
                    "converged": "violet",
                    "unknown": "slate",
                },
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.stage",
                    "states": {
                        "completed": "slate",
                        "scored": "amber",
                        "rewarded": "emerald",
                        "stored": "cyan",
                        "checked": "blue",
                        "converged": "violet",
                        "failed": "red",
                        "running": "blue",
                        "pending": "yellow",
                        "unknown": "slate",
                    },
                },
                "title": "$.display_title",
                "subtitle_icon": "cpu-chip",
                "subtitle": "$.display_subtitle",
                "badge": {"field": "stage", "color_map": "filters.colors"},
                "value": {
                    "path": "$.reward_value",
                    "format": "number",
                },
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.score_pct",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "metadata": [
                    {"label": "Learning Story", "path": "$.story"},
                    {"label": "Stage", "path": "$.stage"},
                    {"label": "Run ID", "path": "$.run_id"},
                    {"label": "Workflow Run ID", "path": "$.workflow_run_id"},
                    {"label": "Target App", "path": "$.target_app"},
                    {"label": "Workflow Type", "path": "$.workflow_type"},
                    {"label": "Graph", "path": "$.graph_id"},
                    {"label": "Profile", "path": "$.profile_id"},
                    {"label": "Profile Version", "path": "$.profile_version"},
                    {"label": "Vulnerability Class", "path": "$.vuln_class"},
                    {"label": "Score", "path": "$.score"},
                    {"label": "Reward", "path": "$.reward_value"},
                    {"label": "Wallet", "path": "$.wallet_id"},
                    {"label": "Transaction", "path": "$.transaction_id"},
                    {"label": "Memory ID", "path": "$.memory_id"},
                    {"label": "Metric", "path": "$.metric_id"},
                    {"label": "Converged", "path": "$.converged"},
                    {"label": "Events", "path": "$.event_count"},
                    {"label": "Artifacts", "path": "$.artifact_count"},
                    {"label": "Last Event", "path": "$.last_event_type"},
                ],
                "tabs": [
                    {
                        "id": "story",
                        "label": "Learning Story",
                        "tool": "ml_get_learning_run",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "detail",
                    },
                    {
                        "id": "timeline",
                        "label": "Event Timeline",
                        "tool": "ml_get_learning_run_timeline",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "list",
                    },
                    {
                        "id": "artifacts",
                        "label": "Artifacts",
                        "tool": "ml_get_learning_run_artifacts",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "list",
                    },
                ],
            },
        },
    }


__all__ = ["learning_view"]
