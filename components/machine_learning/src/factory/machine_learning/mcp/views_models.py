"""Component builders for the ML Models UIView (real training runs).

Declarative components only — same interaction language as the evals
dashboard (trend chart, experiment health with sparkline + regression
badges, run results with drill-down, fine-tuning jobs). Data source is
the durable ``ml_training_runs`` collection via the dashboard tools.
"""

from __future__ import annotations

from typing import Any

_MODEL_TYPE_COLORS = {
    "lightgbm": "emerald", "lstm": "blue", "tcn": "violet",
    "patchtst": "amber", "timegan": "pink",
}
_REGRESSION_COLORS = {
    "regressed": "red", "improved": "emerald", "steady": "blue", "baseline": "gray",
}


def trend_chart() -> dict[str, Any]:
    """Recent training-run metric trend (AUROC/F1) for quick scanning."""
    return {
        "id": "ml-recent-trend",
        "type": "chart",
        "props": {
            "title": "Recent Training Metric",
            "data_tool": "ml_get_dashboard_summary",
            "data_path": "$.series",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Train a model to build a visible metric trend.",
            "className": "mb-3",
        },
    }


def experiment_health() -> dict[str, Any]:
    """Experiment-level grouped health: latest metric, delta, regression."""
    return {
        "id": "ml-experiment-health",
        "type": "item_list",
        "props": {
            "data_tool": "ml_get_dashboard_summary",
            "data_path": "$.experiments",
            "item_key": "experiment_name",
            "empty_icon": "cpu-chip",
            "empty_message": "No training experiments yet. Run can_run_full_pipeline or ml_train_timeseries.",
            "header": {
                "icon": "chart-bar",
                "stats_tool": "ml_get_dashboard_summary",
                "stats_map": {
                    "experiments": "$.overview.experiments",
                    "runs": "$.overview.runs",
                    "regressions": "$.overview.regressions",
                },
            },
            "filters": {
                "field": "regression_state",
                "values": ["regressed", "improved", "steady", "baseline"],
                "colors": dict(_REGRESSION_COLORS),
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.regression_state",
                    "states": dict(_REGRESSION_COLORS),
                },
                "title": "$.experiment_name",
                "subtitle": "$.latest_model_type",
                "badge": {"field": "regression_state", "color_map": "filters.colors"},
                "value": {"path": "$.latest_value", "format": "number"},
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.metric_delta",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "sparkline": {
                    "data_path": "$.recent_values",
                    "color": "indigo",
                    "height": 28,
                    "max_points": 8,
                    "variant": "line",
                },
                "metadata": [
                    {"label": "Metric", "path": "$.primary_metric", "zone": "config"},
                    {"label": "Model Types", "path": "$.model_types", "render_as": "pills", "zone": "config"},
                    {"label": "Source", "path": "$.source", "zone": "config"},
                    {"label": "Runs", "path": "$.runs", "zone": "identity"},
                    {"label": "Best", "path": "$.best_value", "render_as": "score", "zone": "identity"},
                    {"label": "Avg", "path": "$.avg_value", "render_as": "score", "zone": "identity"},
                    {"label": "Latest Run", "path": "$.latest_run_id", "render_as": "copy_id", "zone": "identity"},
                ],
            },
        },
    }


def training_runs() -> dict[str, Any]:
    """Individual training runs with metrics and regression drill-down."""
    return {
        "id": "ml-training-runs",
        "type": "item_list",
        "props": {
            "data_tool": "ml_list_training_runs",
            "data_path": "$.runs",
            "item_key": "run_id",
            "empty_icon": "cpu-chip",
            "empty_message": "No persisted training runs yet.",
            "header": {
                "icon": "cpu-chip",
                "stats_tool": "ml_get_dashboard_summary",
                "stats_map": {
                    "runs": "$.overview.runs",
                    "model types": "$.overview.model_types",
                    "avg metric": "$.overview.avg_metric",
                },
            },
            "filters": {
                "field": "model_type",
                "values": list(_MODEL_TYPE_COLORS),
                "colors": dict(_MODEL_TYPE_COLORS),
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.status",
                    "states": {"completed": "emerald", "running": "blue", "failed": "red"},
                },
                "title": "$.experiment_name",
                "subtitle": "$.model_type",
                "badge": {"field": "model_type", "color_map": "filters.colors"},
                "value": {"path": "$.primary_value", "format": "number"},
                "trend": {
                    "direction": "$.trend_direction",
                    "change_pct": "$.metric_delta",
                    "positive_is_good": True,
                },
            },
            "detail": {
                "metadata": [
                    {"label": "Metric", "path": "$.primary_metric", "zone": "config"},
                    {"label": "AUROC", "path": "$.metrics.auroc", "render_as": "score", "zone": "config"},
                    {"label": "F1", "path": "$.metrics.f1", "render_as": "score", "zone": "config"},
                    {"label": "AUPRC", "path": "$.metrics.auprc", "render_as": "score", "zone": "config"},
                    {"label": "Brier", "path": "$.metrics.brier", "zone": "config"},
                    {"label": "Source", "path": "$.source", "zone": "identity"},
                    {"label": "Window", "path": "$.config.window_size", "zone": "identity"},
                    {"label": "Seed", "path": "$.config.seed", "zone": "identity"},
                    {"label": "Run ID", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Model Path", "path": "$.model_path", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "record", "label": "Full Record",
                        "tool": "ml_get_training_run",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "detail",
                    },
                    {
                        "id": "regression", "label": "Regression",
                        "tool": "ml_get_run_regression",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "alert",
                        "alert_props": {
                            "intent_field": "regressed",
                            "intent_map": {"true": "warning", "false": "success"},
                        },
                    },
                ],
            },
        },
    }


__all__ = ["experiment_health", "training_runs", "trend_chart"]
