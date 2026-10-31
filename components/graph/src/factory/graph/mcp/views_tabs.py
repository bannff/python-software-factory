"""Tab and action builders for Knowledge Graph dashboard."""

from __future__ import annotations

from typing import Any



# ── Read-only tabs (lazy-loaded data) ──────────────────────────────


def graph_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only graph data."""
    return {
        "id": "graph-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "entities", "label": "Entities",
                 "lazy_tool": "graph_find_entities",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "graph_health_check",
                 "result_hints": {"prefer": "stat_grid"}},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def graph_actions() -> list[dict[str, Any]]:
    """Return action definitions for the graph action pane."""
    return [_add_entity(), _add_relationship(), _find_path(), _delete_entity()]


def _add_entity() -> dict[str, Any]:
    return {
        "id": "add-entity", "label": "Add Entity", "icon": "➕",
        "tool": "graph_add_entity", "submit_label": "Add Entity",
        "fields": [
            {"name": "entity_id", "label": "Entity ID", "type": "text",
             "placeholder": "person-1",
             "tooltip": "Unique identifier for the new entity"},
            {"name": "entity_type", "label": "Type", "type": "text",
             "placeholder": "Person",
             "tooltip": "Entity type — used for filtering and queries"},
            {"name": "labels", "label": "Labels",
             "type": "text", "placeholder": "employee, engineer",
             "tooltip": "Comma-separated labels for categorization"},
            {"name": "properties", "label": "Properties (JSON)",
             "type": "textarea", "placeholder": '{"name": "Alice"}',
             "tooltip": "Key-value pairs as JSON object"},
        ],
    }


def _add_relationship() -> dict[str, Any]:
    return {
        "id": "add-rel", "label": "Add Relationship", "icon": "🔗",
        "tool": "graph_add_relationship",
        "submit_label": "Add Relationship",
        "fields": [
            {"name": "relationship_id", "label": "Relationship ID",
             "type": "text", "placeholder": "rel-1",
             "tooltip": "Unique identifier for this relationship"},
            {"name": "relationship_type", "label": "Type",
             "type": "text", "placeholder": "KNOWS",
             "tooltip": "e.g. KNOWS, WORKS_AT, DEPENDS_ON"},
            {"name": "source_id", "label": "Source Entity",
             "type": "text", "placeholder": "person-1",
             "tooltip": "ID of the source (from) entity"},
            {"name": "target_id", "label": "Target Entity",
             "type": "text", "placeholder": "person-2",
             "tooltip": "ID of the target (to) entity"},
            {"name": "properties", "label": "Properties (JSON)",
             "type": "textarea", "placeholder": '{"since": "2024"}',
             "tooltip": "Optional edge properties as JSON"},
        ],
    }


def _find_path() -> dict[str, Any]:
    return {
        "id": "find-path", "label": "Find Shortest Path", "icon": "🔍",
        "tool": "graph_find_path",
        "submit_label": "Find Path",
        "fields": [
            {"name": "source_id", "label": "From Entity",
             "type": "text", "placeholder": "person-1",
             "tooltip": "Starting entity ID"},
            {"name": "target_id", "label": "To Entity",
             "type": "text", "placeholder": "person-2",
             "tooltip": "Destination entity ID"},
            {"name": "max_depth", "label": "Max Depth",
             "type": "number", "placeholder": "5",
             "tooltip": "Maximum hops to search — lower is faster"},
        ],
    }


def _delete_entity() -> dict[str, Any]:
    return {
        "id": "delete-entity", "label": "⚠ Delete Entity", "icon": "🗑️",
        "tool": "graph_delete_entity",
        "submit_label": "Delete",
        "fields": [
            {"name": "entity_id", "label": "Entity ID",
             "type": "text", "placeholder": "person-1",
             "tooltip": "Deletes the entity and all its relationships"},
        ],
    }
