"""Tab and action builders for Storage Browser dashboard.

Exports:
- storage_read_tabs(): read-only tabs (blobs, documents, health, config)
- storage_actions(): write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def _empty(message: str, hint: str = "", icon: str = "") -> str:
    """Static empty-state for tabs that need user input first."""
    icon_html = (
        f'<span class="text-3xl mb-2">{icon}</span>' if icon else ""
    )
    hint_html = (
        f'<p class="text-xs text-base-content/40 mt-1">{hint}</p>'
        if hint else ""
    )
    return (
        f'<div class="flex flex-col items-center justify-center py-8">'
        f'{icon_html}'
        f'<p class="text-base-content/50">{message}</p>'
        f'{hint_html}</div>'
    )


# ── Read-only tabs (lazy-loaded data) ──────────────────────────────


def storage_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only storage data."""
    return {
        "id": "storage-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "blobs", "label": "Blobs",
                 "lazy_tool": "storage_blob_list"},
                {"id": "documents", "label": "Documents",
                 "content": _empty(
                     "Use Search Documents below to query a collection.",
                     "Specify a collection name and query filter.",
                     icon="🔍",
                 )},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "storage_health_check"},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def storage_actions() -> list[dict[str, Any]]:
    """Return action definitions for the storage action pane."""
    return [
        _upload_blob(),
        _delete_blob(),
        _insert_document(),
        _search_documents(),
        _get_blob(),
    ]


def _upload_blob() -> dict[str, Any]:
    return {
        "id": "upload-blob", "label": "Upload Blob", "icon": "📤",
        "tool": "storage_blob_put", "submit_label": "Upload",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "path/to/file.txt",
             "tooltip": "Storage key — use / for folder-like paths"},
            {"name": "data", "label": "Content", "type": "textarea",
             "placeholder": "File content or base64 data…",
             "tooltip": "Raw text or base64-encoded binary content"},
            {"name": "content_type", "label": "Content-Type",
             "type": "text", "placeholder": "text/plain",
             "tooltip": "MIME type — use base64 in type for binary"},
        ],
    }


def _delete_blob() -> dict[str, Any]:
    return {
        "id": "delete-blob", "label": "⚠ Delete Blob", "icon": "🗑️",
        "tool": "storage_blob_delete", "submit_label": "Delete",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "path/to/file.txt",
             "tooltip": "Exact blob key to remove"},
        ],
    }


def _insert_document() -> dict[str, Any]:
    return {
        "id": "insert-doc", "label": "Insert Document", "icon": "📄",
        "tool": "storage_doc_insert", "submit_label": "Insert",
        "fields": [
            {"name": "collection", "label": "Collection",
             "type": "text", "placeholder": "my-collection",
             "tooltip": "Target collection name"},
            {"name": "data", "label": "Data (JSON)",
             "type": "textarea", "placeholder": '{"key": "value"}',
             "tooltip": "Document body as a JSON object"},
            {"name": "doc_id", "label": "Document ID",
             "type": "text",
             "placeholder": "Optional — auto-generated if empty",
             "tooltip": "Leave blank for auto-generated UUID"},
        ],
    }


def _search_documents() -> dict[str, Any]:
    return {
        "id": "search-docs", "label": "Search Documents", "icon": "🔍",
        "tool": "storage_doc_find", "submit_label": "Search",
        "fields": [
            {"name": "collection", "label": "Collection",
             "type": "text", "placeholder": "my-collection",
             "tooltip": "Collection to search within"},
            {"name": "query", "label": "Query (JSON)",
             "type": "textarea",
             "placeholder": '{"status": "active"}',
             "tooltip": "JSON query filter for matching documents"},
            {"name": "limit", "label": "Max Results",
             "type": "range", "min": 1, "max": 100, "value": 25,
             "tooltip": "Cap the number of returned documents"},
        ],
    }


def _get_blob() -> dict[str, Any]:
    return {
        "id": "get-blob", "label": "Get Blob", "icon": "📥",
        "tool": "storage_blob_get", "submit_label": "Fetch",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "path/to/file.txt",
             "tooltip": "Exact blob key to retrieve"},
        ],
    }
