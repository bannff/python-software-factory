"""UIView definitions for Auth brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of multiple collapsible forms.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.models import EmptyInput, ViewsOutput
from .views_tabs import auth_actions, auth_read_tabs


def register(mcp: Any) -> None:
    """Register Auth view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def auth_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Auth brick."""
        return ViewsOutput(views=[
            {
                "id": "auth-manager",
                "name": "Authentication",
                "brick": "auth",
                "icon": "🔐",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "auth-page",
                        "type": "page",
                        "props": {
                            "title": "Authentication",
                            "subtitle": (
                                "Manage tokens, verify credentials,"
                                " and inspect sessions"
                            ),
                            "icon": "🔐",
                            "gradient": "from-yellow-500 to-amber-600",
                            "tooltip": (
                                "Supports Keycloak, Authlib,"
                                " and in-memory backends"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": "Manage authentication and tokens",
                    "nav_label": "Auth",
                    "nav_order": 50,
                },
            },
        ])


def _children() -> list[dict[str, Any]]:
    """Build page children: metrics, verify form, read tabs, action pane."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "auth-stat-backend",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Backend",
                "value": "memory", "icon": "shield-check",
                "tooltip": "Polymorphic — swap to Keycloak, Cognito, etc.",
            },
        },
        {
            "id": "auth-stat-status",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Status",
                "value": "Active", "icon": "check-circle",
                "intent": "success",
                "data_tool": "auth_auth.health_check",
                "tooltip": "Auth backend health status",
            },
        },
        # ── Zone 2: Controls — primary verify form ──
        {
            "id": "auth-verify-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "auth_auth.verify_access_token",
                "title": "Verify Token",
                "submit_label": "Verify Token",
                "fields": [
                    {
                        "name": "token",
                        "label": "Access Token",
                        "type": "textarea",
                        "placeholder": "Paste JWT token to verify...",
                        "tooltip": "JWT or opaque token to validate",
                    },
                    {
                        "name": "required_audience",
                        "label": "Required Audience",
                        "type": "text",
                        "placeholder": "Optional audience claim",
                        "tooltip": "Reject tokens not issued for this audience",
                    },
                ],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        auth_read_tabs(),
        # ── Zone 3: Action pane (token operations) ──
        {
            "id": "auth-actions",
            "type": "action_pane",
            "props": {
                "actions": auth_actions(),
                "default_action": "exchange-token",
            },
        },
    ]
