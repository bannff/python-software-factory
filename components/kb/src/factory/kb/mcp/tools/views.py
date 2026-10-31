"""UIView definitions for KB brick — 3 focused panels."""
from __future__ import annotations
from typing import Any
from factory.mcp_utils.interface import deterministic


def register(mcp: Any) -> None:
    @mcp.tool()
    @deterministic
    def kb_get_views() -> list[dict[str, Any]]:
        """Return panel definitions for the KB brick."""
        return [_search_panel(), _ingest_panel(), _collections_panel()]


def _search_panel() -> dict[str, Any]:
    """KB Search — semantic search + results."""
    return {
        "id": "kb-search", "name": "Knowledge Search",
        "brick": "kb", "icon": "🔍",
        "layout": {"type": "flex", "direction": "column"},
        "components": [{
            "id": "kb-search-page", "type": "page",
            "props": {
                "title": "Knowledge Search",
                "subtitle": "Semantic search across your knowledge base",
                "icon": "🔍", "gradient": "from-teal-500 to-cyan-600",
                "tooltip": "Vector-powered semantic search",
            },
            "children": [
                {"id": "kb-s-docs", "type": "metric", "props": {
                    "zone": "info", "label": "Documents", "value": "0",
                    "icon": "document-text",
                    "data_tool": "kb_get_collection_stats",
                    "metric_key": "document_count",
                    "tooltip": "Total indexed documents",
                }},
                {"id": "kb-s-health", "type": "metric", "props": {
                    "zone": "info", "label": "Health", "value": "—",
                    "icon": "shield-check", "intent": "success",
                    "data_tool": "kb_health_check",
                    "tooltip": "Backend connectivity",
                }},
                {"id": "kb-search-form", "type": "form", "props": {
                    "zone": "controls", "tool": "kb_search",
                    "title": "Semantic Search", "submit_label": "Search",
                    "fields": [
                        {"name": "query", "label": "Query", "type": "text",
                         "placeholder": "What are you looking for?",
                         "tooltip": "Natural language query"},
                        {"name": "limit", "label": "Max Results",
                         "type": "range", "min": 1, "max": 50, "value": 10},
                    ],
                }},
            ],
        }],
        "metadata": {
            "description": "Semantic search across documents",
            "nav_label": "KB Search", "nav_order": 10,
            "panel": {"size_hint": "half", "standalone": True,
                      "category": "data"},
        },
    }


def _ingest_panel() -> dict[str, Any]:
    """KB Ingest — add documents to the knowledge base."""
    return {
        "id": "kb-ingest", "name": "Ingest Documents",
        "brick": "kb", "icon": "📥",
        "layout": {"type": "flex", "direction": "column"},
        "components": [{
            "id": "kb-ingest-page", "type": "page",
            "props": {
                "title": "Ingest Documents",
                "subtitle": "Add documents to the knowledge base",
                "icon": "📥", "gradient": "from-cyan-500 to-blue-500",
                "tooltip": "Content is chunked, embedded, and indexed",
            },
            "children": [
                {"id": "kb-i-docs", "type": "metric", "props": {
                    "zone": "info", "label": "Documents", "value": "0",
                    "icon": "document-text",
                    "data_tool": "kb_get_collection_stats",
                    "metric_key": "document_count",
                    "tooltip": "Total indexed documents",
                }},
                {"id": "kb-i-colls", "type": "metric", "props": {
                    "zone": "info", "label": "Collections", "value": "0",
                    "icon": "rectangle-stack",
                    "data_tool": "kb_get_collection_registry",
                    "tooltip": "Available collections",
                }},
                {"id": "kb-ingest-form", "type": "form", "props": {
                    "zone": "controls", "tool": "kb_ingest",
                    "title": "Ingest Document", "submit_label": "Ingest",
                    "fields": [
                        {"name": "content", "label": "Content",
                         "type": "textarea",
                         "placeholder": "Paste document text…",
                         "tooltip": "Raw text to embed and store"},
                        {"name": "source", "label": "Source",
                         "type": "text", "placeholder": "manual",
                         "tooltip": "Origin label"},
                        {"name": "document_id", "label": "Document ID",
                         "type": "text",
                         "placeholder": "auto-generated if blank",
                         "tooltip": "Custom ID (optional)"},
                    ],
                }},
                {"id": "kb-i-recent", "type": "tabs", "props": {
                    "tabs": [{"id": "recent-docs",
                              "label": "Recent Documents",
                              "lazy_tool": "kb_list_documents"}],
                }},
            ],
        }],
        "metadata": {
            "description": "Add documents to the knowledge base",
            "nav_label": "KB Ingest", "nav_order": 11,
            "panel": {"size_hint": "half", "standalone": True,
                      "category": "data"},
        },
    }


def _collections_panel() -> dict[str, Any]:
    """KB Collections — manage document collections."""
    return {
        "id": "kb-collections", "name": "Collections",
        "brick": "kb", "icon": "📚",
        "layout": {"type": "flex", "direction": "column"},
        "components": [{
            "id": "kb-colls-page", "type": "page",
            "props": {
                "title": "Collections",
                "subtitle": "Manage document collections",
                "icon": "📚", "gradient": "from-blue-500 to-indigo-500",
                "tooltip": "Create, browse, and delete collections",
            },
            "children": [
                {"id": "kb-c-colls", "type": "metric", "props": {
                    "zone": "info", "label": "Collections", "value": "0",
                    "icon": "rectangle-stack",
                    "data_tool": "kb_get_collection_registry",
                    "tooltip": "Total collections",
                }},
                {"id": "kb-c-size", "type": "metric", "props": {
                    "zone": "info", "label": "Size", "value": "—",
                    "icon": "circle-stack", "intent": "muted",
                    "data_tool": "kb_get_collection_stats",
                    "metric_key": "total_size_bytes",
                    "tooltip": "Total storage size",
                }},
                {"id": "kb-c-upsert", "type": "form", "props": {
                    "zone": "controls",
                    "tool": "kb_authoring.upsert_collection",
                    "title": "Save Collection", "submit_label": "Save",
                    "fields": [
                        {"name": "collection_id", "label": "Collection ID",
                         "type": "text", "placeholder": "my-collection"},
                        {"name": "collection_data", "label": "Config (JSON)",
                         "type": "textarea",
                         "placeholder": '{"name": "My Collection"}'},
                    ],
                }},
                {"id": "kb-c-tabs", "type": "tabs", "props": {
                    "active": "collections",
                    "tabs": [
                        {"id": "collections", "label": "Collections",
                         "lazy_tool": "kb_get_collection_registry"},
                        {"id": "health", "label": "Health",
                         "lazy_tool": "kb_health_check"},
                    ],
                }},
                {"id": "kb-c-actions", "type": "action_pane", "props": {
                    "actions": [{
                        "id": "delete-coll",
                        "label": "⚠ Delete Collection", "icon": "🗑️",
                        "tool": "kb_authoring.delete_collection",
                        "submit_label": "Delete",
                        "fields": [
                            {"name": "collection_id",
                             "label": "Collection ID", "type": "text",
                             "placeholder": "collection-to-delete"},
                        ],
                    }],
                    "default_action": "delete-coll",
                }},
            ],
        }],
        "metadata": {
            "description": "Manage document collections",
            "nav_label": "KB Collections", "nav_order": 12,
            "panel": {"size_hint": "full", "standalone": True,
                      "category": "data"},
        },
    }
