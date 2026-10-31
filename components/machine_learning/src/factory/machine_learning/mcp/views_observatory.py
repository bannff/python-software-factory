"""Overview view declaration for the ML Observatory."""
from __future__ import annotations

from typing import Any


def header(subtitle: str) -> dict[str, Any]:
    """Return the persistent Observatory heading used by every mode."""
    return {
        "id": "ml-observatory-header", "type": "card",
        "props": {"title": "ML Observatory", "description": subtitle},
    }


def _metric(key: str, label: str, icon: str) -> dict[str, Any]:
    return {
        "id": f"ml-overview-{key}", "type": "metric",
        "props": {
            "label": label, "icon": icon, "value": "Unknown",
            "data_tool": "ml_get_observatory_summary",
            "data_path": f"$.overview.{key}",
        },
    }


def overview_view() -> dict[str, Any]:
    """Return the availability-aware Observatory overview."""
    metrics = [
        _metric("training_runs", "Training Runs", "cpu-chip"),
        _metric("experiments", "Experiments", "beaker"),
        _metric("receipt_models", "Receipt Models", "cube"),
        _metric("fine_tuning_jobs", "Fine-Tuning Jobs", "adjustments-horizontal"),
        _metric("regressions", "Regressions", "exclamation-triangle"),
        _metric("learning_runs", "Learning Runs", "arrow-path"),
    ]
    return {
        "id": "ml-overview", "name": "Overview", "brick": "machine_learning",
        "icon": "🔭", "layout": {"type": "flex", "direction": "column"},
        "components": [
            header("Training, experiments, models, learning, and provenance in one honest view."),
            *metrics,
            {
                "id": "ml-overview-population", "type": "metric",
                "props": {
                    "label": "Population State", "value": "Unknown",
                    "data_tool": "ml_get_observatory_summary", "data_path": "$.population_state",
                },
            },
            {
                "id": "ml-overview-getting-started", "type": "card",
                "props": {
                    "title": "Start the improvement loop",
                    "description": "Create an immutable dataset artifact → train a model → evaluate it. Ask the assistant to run the relevant MCP operation.",
                },
            },
            {
                "id": "ml-overview-progress", "type": "chart",
                "props": {
                    "title": "Recent Progress", "data_tool": "ml_get_observatory_summary",
                    "xKey": "label", "yKey": "value",
                    "empty_state": "Train or score a run to create a progress series.",
                },
            },
            {
                "id": "ml-overview-sources", "type": "item_list",
                "props": {
                    "data_tool": "ml_get_observatory_summary", "data_path": "$.sources",
                    "item_key": "name", "empty_message": "No source diagnostics available.",
                    "item_layout": {
                        "title": "$.name", "subtitle": "$.durability",
                        "badge": {"field": "health"},
                    },
                    "detail": {"metadata": [
                        {"label": "Freshness", "path": "$.freshness"},
                        {"label": "Diagnostic", "path": "$.error"},
                    ]},
                },
            },
            {
                "id": "ml-overview-attention", "type": "item_list",
                "props": {
                    "data_tool": "ml_get_observatory_summary", "data_path": "$.attention",
                    "item_key": "id", "empty_icon": "check-circle",
                    "empty_message": "No regressions or failed runs need attention.",
                    "item_layout": {"title": "$.title", "subtitle": "$.kind"},
                },
            },
        ],
        "metadata": {
            "description": "Availability-aware ML improvement-loop overview",
            "nav_label": "Overview", "nav_order": 50,
        },
    }


__all__ = ["header", "overview_view"]
