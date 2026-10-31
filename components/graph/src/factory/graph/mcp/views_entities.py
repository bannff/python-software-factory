"""Entity and neighborhood item_list builders for the Graph dashboard.

Split out of :mod:`views.py` so each module stays under
the 200 LOC repo cap. Builders are consumed from
``_dashboard()`` in :mod:`views`.
"""

from __future__ import annotations

from typing import Any


def _entities_list() -> dict[str, Any]:
    return {
        "id": "graph-entities-list",
        "type": "item_list",
        "props": {
            "data_tool": "graph_get_dashboard_summary",
            "data_path": "$.entities",
            "item_key": "entity_id",
            "empty_icon": "cube-transparent",
            "empty_message": "No graph entities recorded yet.",
            "header": {
                "icon": "cube-transparent",
                "stats_tool": "graph_get_dashboard_summary",
                "stats_map": {
                    "nodes": "$.overview.nodes",
                    "edges": "$.overview.edges",
                    "types": "$.overview.entity_types",
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
                "value": {"path": "$.neighbor_count", "format": "number"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Neighbors", "path": "$.neighbor_count", "zone": "identity"},
                    {"label": "Labels", "path": "$.labels", "render_as": "pills", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Created", "path": "$.age_label", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "entity",
                        "label": "Entity",
                        "tool": "graph_get_entity",
                        "args": {"entity_id": "$.entity_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "neighbors",
                        "label": "Neighbors",
                        "tool": "graph_get_entity_context",
                        "args": {"entity_id": "$.entity_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No neighboring entities found for this node.",
                    },
                ],
            },
        },
    }


def _neighborhood_stream() -> dict[str, Any]:
    return {
        "id": "graph-neighborhoods",
        "type": "item_list",
        "props": {
            "data_tool": "graph_get_dashboard_summary",
            "data_path": "$.neighborhoods",
            "item_key": "entity_id",
            "empty_icon": "network",
            "empty_message": "No connected graph neighborhoods yet.",
            "header": {
                "icon": "network",
                "stats_tool": "graph_get_dashboard_summary",
                "stats_map": {
                    "neighborhoods": "$.overview.neighborhoods",
                    "nodes": "$.overview.nodes",
                },
            },
            "filters": {
                "field": "entity_type",
                "values": [
                    "WorkflowRun",
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
                "value": {"path": "$.focus_entity_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Focus", "path": "$.focus_entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }


__all__ = ["_entities_list", "_neighborhood_stream"]
