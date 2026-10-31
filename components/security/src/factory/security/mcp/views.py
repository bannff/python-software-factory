"""UIView definitions for Security brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of multiple collapsible forms.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from .contracts.base import EmptyInput
from .contracts.views import ViewsOutput

from .views_tabs import security_actions, security_read_tabs


def register(mcp: Any) -> None:
    """Register Security view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def security_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Security brick."""
        return ViewsOutput(views=[
            {
                "id": "security-dashboard",
                "name": "Security Operations",
                "brick": "security",
                "icon": "🛡️",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "security-page",
                        "type": "page",
                        "props": {
                            "title": "Security Operations",
                            "subtitle": (
                                "Threat modeling, code analysis,"
                                " and vulnerability management"
                            ),
                            "icon": "🛡️",
                            "gradient": "from-red-500 to-orange-500",
                            "tooltip": (
                                "LLM-powered security analysis"
                                " with multiple scan types"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": (
                        "Threat modeling, code analysis,"
                        " and findings"
                    ),
                    "nav_label": "Security",
                    "nav_order": 25,
                },
            },
        ])


def _children() -> list[dict[str, Any]]:
    """Build page children: metrics, scan form, read tabs, action pane."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "security-stat-findings",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Findings",
                "value": "0", "icon": "document",
                "intent": "critical",
                "tooltip": (
                    "Total security findings across all scans"
                ),
            },
        },
        {
            "id": "security-stat-scans",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Analyses",
                "value": "0", "icon": "chart",
                "tooltip": "Number of completed security analyses",
            },
        },
        # ── Zone 2: Controls — primary scan form ──
        {
            "id": "security-scan-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "security_security.analyze",
                "title": "Quick Scan",
                "submit_label": "Quick Scan",
                "fields": [
                    {
                        "name": "target",
                        "label": "Target",
                        "type": "text",
                        "placeholder": (
                            "https://example.com or /path/to/code"
                        ),
                        "tooltip": (
                            "URL for recon, file path for code"
                            " analysis, or text for threat modeling"
                        ),
                    },
                ],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        security_read_tabs(),
        # ── Zone 3: Action pane (polymorphic write operations) ──
        {
            "id": "security-actions",
            "type": "action_pane",
            "props": {
                "actions": security_actions(),
                "default_action": "run-analysis",
            },
        },
    ]
