"""Typed UIView definitions for the Metrics brick."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.deterministic import EmptyInput, ViewsOutput


def register(mcp: Any) -> None:
    """Register Metrics view definitions."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def metrics_get_views() -> ToolResult[ViewsOutput]:
        return ok(ViewsOutput(views=[{"id": "metrics-dashboard", "name": "Metrics & Coverage", "brick": "metrics", "icon": "📊", "layout": {"type": "flex", "direction": "column"}, "components": [_item_list()], "metadata": {"description": "Portfolio metrics and coverage tracking", "nav_label": "Metrics", "nav_order": 55}}]))


def _item_list() -> dict[str, Any]:
    return {"id": "metrics-list", "type": "item_list", "props": {"data_tool": "metrics_get_registry", "item_snapshot_tool": "metrics_get_snapshot", "item_snapshot_args": {"metric_id": "$.id"}, "snapshot_merge_path": "snapshot", "item_key": "id", "empty_icon": "chart-bar-square", "empty_message": "No metrics tracked yet. The agent records metrics during security scans and evaluations.", "header": {"icon": "chart-bar", "stats_tool": "metrics_health_check", "stats_map": {"definitions": "$.definitions", "data points": "$.store.total_points"}}, "filters": {"field": "category", "values": ["coverage", "risk", "quality", "performance"], "colors": {"coverage": "blue", "risk": "orange", "quality": "emerald", "performance": "purple"}}, "item_layout": {"status_dot": {"value_path": "$.snapshot.current_value", "thresholds": {"warning": "$.thresholds.warning", "critical": "$.thresholds.critical"}}, "title": "$.name", "subtitle": "$.format", "badge": {"field": "category", "color_map": "filters.colors"}, "value": {"path": "$.snapshot.current_value", "format": "$.format"}, "trend": {"direction": "$.snapshot.trend", "change_pct": "$.snapshot.change_pct", "positive_is_good": True}}, "detail": {"sparkline": {"color": "indigo", "height": 32, "max_points": 20, "variant": "bar"}, "metadata": [{"label": "Thresholds", "path": "$.thresholds", "render_as": "threshold", "zone": "config"}, {"label": "Source", "path": "$.source_brick", "render_as": "pills", "zone": "config"}, {"label": "Fed by", "path": "$.input_tool", "render_as": "model_chip", "zone": "config"}, {"label": "Domain", "path": "$.domain", "zone": "identity"}, {"label": "Format", "path": "$.format", "render_as": "pills", "zone": "identity"}, {"label": "Type", "path": "$.metric_type", "render_as": "pills", "zone": "identity"}, {"label": "Points", "path": "$.snapshot.data_points", "zone": "identity"}, {"label": "Formula", "path": "$.composite_formula", "render_as": "popover", "zone": "identity"}], "tabs": [{"id": "trend", "label": "Trend", "tool": "metrics_get_trend", "args": {"metric_id": "$.id", "window": "7d", "granularity": "1d"}, "render_as": "chart", "chart_props": {"chart_type": "line", "x_key": "start", "y_key": "value", "color": "indigo", "height": 160, "empty_message": "No trend data yet — record values to populate"}}, {"id": "drift", "label": "Drift & Regression", "tool": "metrics_detect_drift", "args": {"metric_id": "$.id", "baseline_period": "7d", "threshold": 0.1}, "render_as": "alert", "alert_props": {"intent_field": "drifted", "intent_map": {"true": "warning", "false": "success"}}}]}}}
