"""Tab and action builders for KB dashboard.

Exports:
- kb_read_tabs(): read-only tabs component (documents, collections, health)
- kb_actions(): list of write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



# ── Read-only tabs ──────────────────────────────────────────────────


def kb_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only KB data."""
    return {
        "id": "kb-read-tabs",
        "type": "tabs",
        "props": {
            "active": "documents",
            "tabs": [
                {"id": "documents", "label": "Documents",
                 "lazy_tool": "kb_list_documents",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "collections", "label": "Collections",
                 "lazy_tool": "kb_get_collection_registry",
                 "result_hints": {"searchable": True}},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "kb_health_check",
                 "result_hints": {"prefer": "stat_grid"}},
            ],
        },
    }


# ── Write-operation actions for the action_pane ─────────────────────


def kb_actions() -> list[dict[str, Any]]:
    """Return action definitions for the KB action pane."""
    return [
        _ingest(),
        _get_document(),
        _delete_document(),
        _upsert_collection(),
        _delete_collection(),
    ]


def _ingest() -> dict[str, Any]:
    return {
        "id": "ingest", "label": "Ingest Document", "icon": "📥",
        "tool": "kb_ingest", "submit_label": "Ingest",
        "description": (
            "Add a document to the knowledge base. Content is"
            " chunked, embedded, and indexed for semantic search."
        ),
        "fields": [
            {"name": "content", "label": "Content", "type": "textarea",
             "placeholder": "Paste or type document text\u2026",
             "tooltip": "Raw text content to embed and store",
             "description": "Plain text, markdown, or structured content"},
            {"name": "source", "label": "Source", "type": "text",
             "placeholder": "manual",
             "tooltip": "Origin label \u2014 e.g. 'manual', 'api', 'crawler'"},
            {"name": "document_id", "label": "Document ID (optional)",
             "type": "text", "placeholder": "auto-generated if blank",
             "tooltip": "Custom ID \u2014 leave empty for auto-generated UUID"},
        ],
    }


def _get_document() -> dict[str, Any]:
    return {
        "id": "get-doc", "label": "Get Document", "icon": "📄",
        "tool": "kb_get_document", "submit_label": "Fetch",
        "fields": [
            {"name": "document_id", "label": "Document ID", "type": "text",
             "placeholder": "Enter document ID",
             "tooltip": "Retrieve a single document by its unique ID"},
        ],
    }


def _delete_document() -> dict[str, Any]:
    return {
        "id": "delete-doc", "label": "\u26a0 Delete Document", "icon": "🗑\ufe0f",
        "tool": "kb_delete_document", "submit_label": "Delete",
        "fields": [
            {"name": "document_id", "label": "Document ID", "type": "text",
             "placeholder": "ID of document to remove",
             "tooltip": "Permanently removes the document and its embeddings"},
        ],
    }


def _upsert_collection() -> dict[str, Any]:
    return {
        "id": "upsert-coll", "label": "Save Collection", "icon": "💾",
        "tool": "kb_authoring.upsert_collection",
        "submit_label": "Save Collection",
        "fields": [
            {"name": "collection_id", "label": "Collection ID",
             "type": "text", "placeholder": "my-collection",
             "tooltip": "Unique identifier for the collection"},
            {"name": "collection_data", "label": "Collection Config (JSON)",
             "type": "textarea",
             "placeholder": '{"name": "My Collection", "description": "..."}',
             "tooltip": "JSON object with collection configuration fields"},
        ],
    }


def _delete_collection() -> dict[str, Any]:
    return {
        "id": "delete-coll", "label": "\u26a0 Delete Collection", "icon": "🗑\ufe0f",
        "tool": "kb_authoring.delete_collection",
        "submit_label": "Delete Collection",
        "fields": [
            {"name": "collection_id", "label": "Collection ID",
             "type": "text", "placeholder": "collection-to-delete",
             "tooltip": "Permanently removes the collection and all documents"},
        ],
    }
