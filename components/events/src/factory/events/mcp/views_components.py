"""Component-tree builders for the Events dashboard.

Split out of :mod:`views.py` so each module stays under
the 200 LOC repo cap. Imports the subscription and graph
context streams from :mod:`views_streams`.
"""

from __future__ import annotations

from typing import Any

from .views_streams import _graph_context_stream, _subscriptions_list
from .views_tabs import events_actions, events_read_tabs


def _children() -> list[dict[str, Any]]:
    """Build dashboard children for Events."""
    return [
        _event_type_chart(),
        {
            "id": "events-publish-form",
            "type": "form",
            "props": {
                "tool": "events_publish",
                "title": "Publish Event",
                "submit_label": "Publish Event",
                "description": (
                    "Publish a correlated event into the shared timeline."
                    " Matching subscriptions will dispatch automatically."
                ),
                "fields": [
                    {
                        "name": "event_type",
                        "label": "Event Type",
                        "type": "text",
                        "placeholder": "user.created",
                        "tooltip": "Dot-separated event type for routing",
                        "description": "e.g. user.created, order.completed",
                    },
                    {
                        "name": "source",
                        "label": "Source",
                        "type": "text",
                        "placeholder": "my-service",
                        "tooltip": "Originating service or component",
                    },
                    {
                        "name": "attributes",
                        "label": "Attributes (JSON)",
                        "type": "textarea",
                        "placeholder": '{"run_id": "run-123", "env_id": "env-456"}',
                        "tooltip": "Optional correlation metadata written into durable history",
                    },
                    {
                        "name": "payload",
                        "label": "Payload (JSON)",
                        "type": "textarea",
                        "placeholder": "{}",
                        "tooltip": "JSON payload attached to the event",
                    },
                ],
            },
        },
        _events_list(),
        _subscriptions_list(),
        _graph_context_stream(),
        events_read_tabs(),
        {
            "id": "events-actions",
            "type": "action_pane",
            "props": {
                "actions": events_actions(),
                "default_action": "replay-event",
            },
        },
    ]


def _event_type_chart() -> dict[str, Any]:
    return {
        "id": "events-type-mix",
        "type": "chart",
        "props": {
            "title": "Event Type Mix",
            "data_tool": "events_get_dashboard_summary",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Publish an event to populate the shared timeline.",
            "className": "mb-3",
        },
    }


def _events_list() -> dict[str, Any]:
    return {
        "id": "events-stream-list",
        "type": "item_list",
        "props": {
            "data_tool": "events_get_dashboard_summary",
            "data_path": "$.events",
            "item_key": "event_id",
            "empty_icon": "bolt",
            "empty_message": "No events recorded yet.",
            "header": {
                "icon": "bolt",
                "stats_tool": "events_get_dashboard_summary",
                "stats_map": {
                    "events": "$.overview.events",
                    "sources": "$.overview.sources",
                    "subscriptions": "$.overview.subscriptions",
                },
            },
            "filters": {
                "field": "source",
                "values": ["workflow", "sandbox", "games", "blockchain", "events"],
                "colors": {
                    "workflow": "blue",
                    "sandbox": "emerald",
                    "games": "amber",
                    "blockchain": "violet",
                    "events": "slate",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.event_type",
                "subtitle": "$.source",
                "badge": {"field": "source", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.age_label", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Event", "path": "$.event_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.event_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Source", "path": "$.source", "render_as": "pills", "zone": "identity"},
                    {"label": "Tenant", "path": "$.tenant_id", "zone": "identity"},
                    {"label": "Principal", "path": "$.principal_id", "zone": "identity"},
                    {"label": "Correlation", "path": "$.correlation_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Payload", "path": "$.payload", "render_as": "popover", "zone": "config"},
                    {"label": "Metadata", "path": "$.metadata", "render_as": "popover", "zone": "config"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "history",
                        "label": "History",
                        "tool": "events_get_event_history_entry",
                        "args": {"event_id": "$.event_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "event",
                        "label": "Live Event",
                        "tool": "events_get_event",
                        "args": {"event_id": "$.event_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "graph",
                        "label": "Graph",
                        "tool": "events_get_event_graph_context",
                        "args": {"event_id": "$.event_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No related graph entities found for this event yet.",
                    },
                ],
            },
        },
    }


__all__ = ["_children", "_event_type_chart", "_events_list"]
