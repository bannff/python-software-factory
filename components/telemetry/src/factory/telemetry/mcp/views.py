"""UIView definitions for Telemetry brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of multiple collapsible forms.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts.base import EmptyInput, JsonObject
from .contracts.deterministic import ViewsOutput
from .views_tabs import telemetry_actions, telemetry_read_tabs


def register(mcp: Any) -> None:
    """Register Telemetry view definitions."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def telemetry_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Telemetry brick."""
        return {"views": [
            {
                "id": "telemetry-dashboard",
                "name": "Observability",
                "brick": "telemetry",
                "icon": "📡",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "telemetry-page",
                        "type": "page",
                        "props": {
                            "title": "Observability",
                            "subtitle": (
                                "Distributed tracing, metrics,"
                                " and telemetry via OpenTelemetry"
                            ),
                            "icon": "📡",
                            "gradient": "from-lime-500 to-green-600",
                            "tooltip": (
                                "OTLP-compatible with W3C"
                                " TraceContext propagation"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": (
                        "View traces and observability data"
                    ),
                    "nav_label": "Observability",
                    "nav_order": 65,
                },
            },
        ]}


def _children() -> list[dict[str, Any]]:
    """Build page children: metrics, refresh form, read tabs, action pane."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "telemetry-stat-spans",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Metrics",
                "value": "—", "icon": "chart-bar",
                "data_tool": "telemetry_get_metric_registry",
                "tooltip": "Registered metric definitions",
            },
        },
        {
            "id": "telemetry-stat-exporters",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Exporters",
                "value": "—", "icon": "arrow-up-tray",
                "data_tool": "telemetry_get_exporter_registry",
                "tooltip": "Configured OTLP exporters",
            },
        },
        {
            "id": "telemetry-stat-health",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Health",
                "value": "—", "icon": "shield-check",
                "intent": "success",
                "data_tool": "telemetry_health_check",
                "tooltip": "Telemetry subsystem health",
            },
        },
        # ── Zone 2: Controls — primary refresh form ──
        {
            "id": "telemetry-query-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "telemetry_get_metrics_summary",
                "title": "Metrics Snapshot",
                "submit_label": "Refresh Metrics",
                "description": (
                    "Pull the latest metrics snapshot from all"
                    " registered OTLP sources and exporters."
                ),
                "fields": [],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        telemetry_read_tabs(),
        # ── Zone 3: Action pane (polymorphic write operations) ──
        {
            "id": "telemetry-actions",
            "type": "action_pane",
            "props": {
                "actions": telemetry_actions(),
                "default_action": "record-llm",
            },
        },
    ]
