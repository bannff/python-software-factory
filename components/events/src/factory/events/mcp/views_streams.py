"""Subscription and graph-context stream builders for the Events dashboard.

Split out of :mod:`views.py` to keep each module under the
200 LOC repo cap. These builders are referenced from
:mod:`views_components` and indirectly from the
``events_get_views`` tool registered in :mod:`views`.
"""

from __future__ import annotations

from typing import Any


def _subscriptions_list() -> dict[str, Any]:
    return {
        "id": "events-subscriptions",
        "type": "item_list",
        "props": {
            "data_tool": "events_get_dashboard_summary",
            "data_path": "$.subscriptions",
            "item_key": "subscription_id",
            "empty_icon": "bell",
            "empty_message": "No subscriptions registered.",
            "header": {
                "icon": "bell",
                "stats_tool": "events_get_dashboard_summary",
                "stats_map": {
                    "subscriptions": "$.overview.subscriptions",
                    "sources": "$.overview.sources",
                },
            },
            "filters": {
                "field": "enabled",
                "values": [True, False],
                "colors": {"true": "emerald", "false": "gray"},
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.subscription_id",
                "subtitle": "$.event_type",
                "badge": {"field": "enabled", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.handler", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Subscription", "path": "$.subscription_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Event Type", "path": "$.event_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Handler", "path": "$.handler", "render_as": "copy_id", "zone": "config"},
                    {"label": "Priority", "path": "$.priority", "zone": "config"},
                    {"label": "Filters", "path": "$.has_filters", "zone": "config"},
                    {"label": "Description", "path": "$.description", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }


def _graph_context_stream() -> dict[str, Any]:
    return {
        "id": "events-graph-context",
        "type": "item_list",
        "props": {
            "data_tool": "events_get_dashboard_summary",
            "data_path": "$.related_graph_entities",
            "item_key": "entity_id",
            "empty_icon": "network",
            "empty_message": "No graph-linked entities have been resolved from event history yet.",
            "header": {
                "icon": "network",
                "stats_tool": "events_get_dashboard_summary",
                "stats_map": {
                    "entities": "$.overview.graph_entities",
                    "events": "$.overview.events",
                },
            },
            "filters": {
                "field": "entity_type",
                "values": [
                    "WorkflowRun",
                    "WorkflowDefinition",
                    "SandboxEnvironment",
                    "GameSession",
                    "Transaction",
                    "Wallet",
                    "Bounty",
                    "Metric",
                    "Finding",
                ],
                "colors": {
                    "WorkflowRun": "blue",
                    "WorkflowDefinition": "sky",
                    "SandboxEnvironment": "emerald",
                    "GameSession": "amber",
                    "Transaction": "violet",
                    "Wallet": "purple",
                    "Bounty": "rose",
                    "Metric": "indigo",
                    "Finding": "red",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.title",
                "subtitle": "$.subtitle",
                "badge": {"field": "entity_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.focus_event_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Event", "path": "$.focus_event_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }


__all__ = ["_subscriptions_list", "_graph_context_stream"]
