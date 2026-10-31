"""UIView definitions for Integrations brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of tabs with redundant Run buttons.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import deterministic

from .views_tabs import integrations_actions, integrations_read_tabs


def register(mcp: Any) -> None:
    """Register Integrations view definitions."""

    @mcp.tool()
    @deterministic
    def integrations_get_views() -> list[dict[str, Any]]:
        """Return UIView definitions for the Integrations brick."""
        return [
            {
                "id": "integrations-dashboard",
                "name": "Integrations",
                "brick": "integrations",
                "icon": "🔌",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "integrations-page",
                        "type": "page",
                        "props": {
                            "title": "Integrations",
                            "subtitle": (
                                "Connect external services via"
                                " REST, GraphQL, webhooks, and AWS"
                            ),
                            "icon": "🔌",
                            "gradient": "from-pink-500 to-rose-500",
                            "tooltip": (
                                "Polymorphic connectors with"
                                " auto-retry and health checks"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": "Manage external service connectors",
                    "nav_label": "Integrations",
                    "nav_order": 60,
                },
            },
        ]


def _children() -> list[dict[str, Any]]:
    """Build page children: metrics, register form, read tabs, action pane."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "integrations-stat-count",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Connectors",
                "value": "0", "icon": "list",
                "data_tool": "integrations_integrations_list",
                "tooltip": "Total registered connectors",
            },
        },
        {
            "id": "integrations-stat-types",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Types",
                "value": "REST · GraphQL · Webhook",
                "icon": "default",
                "tooltip": "Supported connector transport types",
            },
        },
        # ── Zone 2: Controls — primary register form ──
        {
            "id": "integrations-create-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "integrations_integrations_register",
                "title": "Register Connector",
                "submit_label": "Register Connector",
                "fields": [
                    {
                        "name": "connector_id",
                        "label": "Connector ID",
                        "type": "text",
                        "placeholder": "my-api",
                        "tooltip": "Unique identifier for this connector",
                    },
                    {
                        "name": "name",
                        "label": "Name",
                        "type": "text",
                        "placeholder": "My API Service",
                        "tooltip": "Human-readable display name",
                    },
                    {
                        "name": "connector_type",
                        "label": "Type",
                        "type": "select",
                        "options": [
                            {"value": "rest", "label": "🔌 REST API"},
                            {"value": "graphql", "label": "📊 GraphQL"},
                            {"value": "webhook", "label": "🔔 Webhook"},
                        ],
                        "tooltip": "Transport protocol for this connector",
                    },
                    {
                        "name": "base_url",
                        "label": "Base URL",
                        "type": "text",
                        "placeholder": "https://api.example.com",
                        "tooltip": "Root URL — paths are appended to this",
                    },
                    {
                        "name": "auth_type",
                        "label": "Auth Type",
                        "type": "select",
                        "options": [
                            {"value": "none", "label": "None"},
                            {"value": "bearer", "label": "Bearer Token"},
                            {"value": "api_key", "label": "API Key"},
                            {"value": "basic", "label": "Basic Auth"},
                        ],
                        "tooltip": "Authentication method for the connector",
                    },
                ],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        integrations_read_tabs(),
        # ── Zone 3: Action pane (polymorphic write operations) ──
        {
            "id": "integrations-actions",
            "type": "action_pane",
            "props": {
                "actions": integrations_actions(),
                "default_action": "connect",
            },
        },
    ]
