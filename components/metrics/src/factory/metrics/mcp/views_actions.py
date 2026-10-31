"""Action pane builders for Metrics dashboard.

Exports:
- metrics_actions(): list of write-operation action dicts for action_pane

Split from views_tabs.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def metrics_actions() -> list[dict[str, Any]]:
    """Return action definitions for the metrics action pane."""
    return [
        _record_metric(), _define_metric(), _detect_drift(),
    ]


def _record_metric() -> dict[str, Any]:
    return {
        "id": "record-metric",
        "label": "Record Metric",
        "icon": "📈",
        "tool": "metrics_record",
        "submit_label": "Record",
        "fields": [
            {
                "name": "metric_id", "label": "Metric ID", "type": "text",
                "placeholder": "coverage_score",
                "tooltip": "ID of the metric to record a value for",
            },
            {
                "name": "value", "label": "Value", "type": "number",
                "placeholder": "42.0",
                "tooltip": "Numeric value to record",
            },
        ],
    }


def _define_metric() -> dict[str, Any]:
    return {
        "id": "define-metric",
        "label": "Define Metric",
        "icon": "📋",
        "tool": "metrics_define_metric",
        "submit_label": "Define",
        "fields": [
            {
                "name": "definition", "label": "Definition (JSON)",
                "type": "textarea",
                "placeholder": '{"id": "my_metric", "name": "My Metric", '
                '"description": "...", "metric_type": "gauge"}',
                "tooltip": "Full metric definition as JSON object",
            },
        ],
    }


def _detect_drift() -> dict[str, Any]:
    return {
        "id": "detect-drift",
        "label": "Detect Drift",
        "icon": "🔍",
        "tool": "metrics_detect_drift",
        "submit_label": "Detect",
        "fields": [
            {
                "name": "metric_id", "label": "Metric ID", "type": "text",
                "placeholder": "coverage_score",
                "tooltip": "Metric to check for drift",
            },
            {
                "name": "baseline_period", "label": "Baseline Period",
                "type": "text", "placeholder": "7d",
                "tooltip": "Reference period for comparison",
            },
            {
                "name": "current_period", "label": "Current Period",
                "type": "text", "placeholder": "24h",
                "tooltip": "Recent period to compare against baseline",
            },
            {
                "name": "threshold", "label": "Threshold",
                "type": "number", "placeholder": "0.1",
                "tooltip": "Drift threshold (0.1 = 10% change)",
            },
        ],
    }
