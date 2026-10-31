"""Tab and action builders for Integrations dashboard.

Exports:
- integrations_read_tabs(): read-only tabs (connectors, capabilities, health)
- integrations_actions(): write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def integrations_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only integrations data."""
    return {
        "id": "integrations-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "connectors", "label": "Connectors",
                 "lazy_tool": "integrations_integrations_list"},
                {"id": "capabilities", "label": "Capabilities",
                 "lazy_tool": "integrations_get_capabilities"},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "integrations_health_check"},
            ],
        },
    }


def integrations_actions() -> list[dict[str, Any]]:
    """Return action definitions for the integrations action pane."""
    return [
        _connect(), _disconnect(), _send_request(),
        _lookup(), _unregister(),
    ]


def _connect() -> dict[str, Any]:
    return {
        "id": "connect", "label": "Connect", "icon": "🔌",
        "tool": "integrations_integrations_connect",
        "submit_label": "Connect",
        "fields": [
            {"name": "connector_id", "label": "Connector ID",
             "type": "text", "placeholder": "my-api",
             "tooltip": "ID of the registered connector to connect"},
        ],
    }


def _disconnect() -> dict[str, Any]:
    return {
        "id": "disconnect", "label": "Disconnect", "icon": "🔓",
        "tool": "integrations_integrations_disconnect",
        "submit_label": "Disconnect",
        "fields": [
            {"name": "connector_id", "label": "Connector ID",
             "type": "text", "placeholder": "my-api",
             "tooltip": "ID of the connector to disconnect"},
        ],
    }


def _send_request() -> dict[str, Any]:
    return {
        "id": "send-request", "label": "Send Request", "icon": "📤",
        "tool": "integrations_integrations_call",
        "submit_label": "Send Request",
        "fields": [
            {"name": "connector_id", "label": "Connector ID",
             "type": "text", "placeholder": "my-api",
             "tooltip": "Connector to route the request through"},
            {"name": "method", "label": "Method", "type": "select",
             "options": [
                 {"value": "GET", "label": "GET"},
                 {"value": "POST", "label": "POST"},
                 {"value": "PUT", "label": "PUT"},
                 {"value": "PATCH", "label": "PATCH"},
                 {"value": "DELETE", "label": "DELETE"},
             ],
             "tooltip": "HTTP method for the outbound request"},
            {"name": "path", "label": "Path", "type": "text",
             "placeholder": "/v1/resource",
             "tooltip": "Request path appended to the connector base URL"},
            {"name": "data", "label": "Body (JSON)", "type": "textarea",
             "placeholder": '{"key": "value"}',
             "tooltip": "JSON request body — POST, PUT, PATCH"},
        ],
    }


def _lookup() -> dict[str, Any]:
    return {
        "id": "lookup", "label": "Lookup Connector", "icon": "🔍",
        "tool": "integrations_integrations_get",
        "submit_label": "Lookup",
        "fields": [
            {"name": "connector_id", "label": "Connector ID",
             "type": "text", "placeholder": "my-api",
             "tooltip": "Retrieve full configuration for a connector"},
        ],
    }


def _unregister() -> dict[str, Any]:
    return {
        "id": "unregister", "label": "⚠ Unregister", "icon": "🗑️",
        "tool": "integrations_integrations_unregister",
        "submit_label": "Unregister",
        "fields": [
            {"name": "connector_id", "label": "Connector ID",
             "type": "text", "placeholder": "my-api",
             "tooltip": "Permanently remove a connector registration"},
        ],
    }
