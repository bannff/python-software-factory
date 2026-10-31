"""Chart, viewer, and action-pane builders for the Graph dashboard."""
from __future__ import annotations

from typing import Any

from .views_tabs import graph_actions


def _entity_type_chart() -> dict[str, Any]:
    return {
        "id": "graph-entity-type-mix", "type": "chart",
        "props": {
            "title": "Entity Type Mix", "data_tool": "graph_get_dashboard_summary",
            "xKey": "label", "yKey": "value",
            "empty_state": "Add graph entities to populate the topology view.",
            "className": "mb-3",
        },
    }


def _graph_viewer() -> dict[str, Any]:
    return {
        "id": "graph-viewer", "type": "graph_viewer",
        "props": {
            "data_tool": "graph_find_entities", "neighbors_tool": "graph_get_neighbors",
            "max_nodes": 100, "layout": "spring", "node_size": 20,
            "show_labels": True, "animate_layout": True,
        },
    }


def _action_pane() -> dict[str, Any]:
    return {
        "id": "graph-actions", "type": "action_pane",
        "props": {"actions": graph_actions(), "default_action": "add-entity"},
    }


__all__ = ["_entity_type_chart", "_graph_viewer", "_action_pane"]
