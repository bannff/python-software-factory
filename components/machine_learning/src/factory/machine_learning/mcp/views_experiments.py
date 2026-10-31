"""Experiments view declaration for the ML Observatory."""
from __future__ import annotations

from typing import Any

from .views_models import experiment_health, training_runs
from .views_observatory import header


def experiments_view() -> dict[str, Any]:
    """Return grouped experiment progress plus receipt drill-down."""
    health = experiment_health()
    health["props"]["data_tool"] = "ml_get_observatory_summary"
    health["props"]["header"]["stats_tool"] = "ml_get_observatory_summary"
    runs = training_runs()
    runs["props"]["data_tool"] = "ml_get_observatory_summary"
    runs["props"]["data_path"] = "$.training_runs"
    runs["props"]["header"]["stats_tool"] = "ml_get_observatory_summary"
    runs["props"]["header"]["stats_map"] = {
        "runs": "$.overview.training_runs",
        "experiments": "$.overview.experiments",
        "regressions": "$.overview.regressions",
    }
    return {
        "id": "ml-experiments", "name": "Experiments", "brick": "machine_learning",
        "icon": "🧪", "layout": {"type": "flex", "direction": "column"},
        "components": [
            header("Compare experiment families, scores, deltas, and predecessor evidence."),
            health, runs,
        ],
        "metadata": {
            "description": "Longitudinal experiment and training-run progress",
            "nav_label": "Experiments", "nav_order": 51,
        },
    }


__all__ = ["experiments_view"]
