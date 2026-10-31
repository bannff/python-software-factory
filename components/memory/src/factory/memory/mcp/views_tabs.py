"""Tab and action builders for Memory dashboard.

Exports:
- memory_read_tabs(): read-only tabs component (browse, stats, health)
- memory_actions(): list of write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def _empty(message: str, hint: str = "") -> str:
    """Static empty-state for tabs that need user input first."""
    hint_html = (
        f'<p class="text-xs text-base-content/40 mt-1">{hint}</p>'
        if hint else ""
    )
    return (
        f'<div class="flex flex-col items-center justify-center py-8">'
        f'<p class="text-base-content/50">{message}</p>'
        f'{hint_html}</div>'
    )


# ── Read-only tabs (lazy-loaded data) ──────────────────────────────


def memory_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only memory data."""
    return {
        "id": "memory-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "browse", "label": "Browse Memories",
                 "content": _empty(
                     "Use Store Memory below to add entries,",
                     "then search via the query form above.",
                 )},
                {"id": "stats", "label": "Statistics",
                 "lazy_tool": "memory_memory_stats"},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "memory_health_check"},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def memory_actions() -> list[dict[str, Any]]:
    """Return action definitions for the memory action pane."""
    return [
        _store_memory(),
        _fetch_memory(),
        _delete_memory(),
        _delete_user_memories(),
        _consolidate(),
    ]


def _store_memory() -> dict[str, Any]:
    return {
        "id": "store-memory", "label": "Store Memory", "icon": "💾",
        "tool": "memory_memory_store",
        "submit_label": "Store",
        "fields": [
            {"name": "user_id", "label": "User ID", "type": "text",
             "placeholder": "default",
             "tooltip": "Owner of this memory — scopes storage per user"},
            {"name": "content", "label": "Content", "type": "textarea",
             "placeholder": "Memory content to store...",
             "tooltip": "The text content to persist as a memory entry"},
            {"name": "memory_type", "label": "Memory Type", "type": "select",
             "options": [
                 {"value": "short_term", "label": "Short Term"},
                 {"value": "long_term", "label": "Long Term"},
                 {"value": "episodic", "label": "Episodic"},
             ],
             "tooltip": "Short-term fades, long-term persists, episodic "
                        "captures events"},
            {"name": "category", "label": "Category", "type": "select",
             "options": [
                 {"value": "preference", "label": "Preference"},
                 {"value": "fact", "label": "Fact"},
                 {"value": "summary", "label": "Summary"},
                 {"value": "context", "label": "Context"},
                 {"value": "custom", "label": "Custom"},
             ],
             "tooltip": "Classify the memory for filtered retrieval"},
            {"name": "ttl_seconds", "label": "TTL (seconds)",
             "type": "number", "placeholder": "3600",
             "tooltip": "Auto-expire after N seconds — leave empty for "
                        "no expiry"},
        ],
    }


def _fetch_memory() -> dict[str, Any]:
    return {
        "id": "fetch-memory", "label": "Fetch Memory", "icon": "🔍",
        "tool": "memory_memory_get",
        "submit_label": "Fetch",
        "fields": [
            {"name": "memory_id", "label": "Memory ID", "type": "text",
             "placeholder": "mem-abc123",
             "tooltip": "Exact ID of the memory entry to retrieve"},
        ],
    }


def _delete_memory() -> dict[str, Any]:
    return {
        "id": "delete-memory", "label": "Delete Memory", "icon": "🗑️",
        "tool": "memory_memory_delete",
        "submit_label": "Delete",
        "fields": [
            {"name": "memory_id", "label": "Memory ID", "type": "text",
             "placeholder": "mem-abc123",
             "tooltip": "ID of the memory to permanently remove"},
        ],
    }


def _delete_user_memories() -> dict[str, Any]:
    return {
        "id": "delete-user", "label": "⚠ Delete User Memories",
        "icon": "⚠️",
        "tool": "memory_memory_delete_user",
        "submit_label": "Delete All",
        "fields": [
            {"name": "user_id", "label": "User ID", "type": "text",
             "placeholder": "default",
             "tooltip": "Permanently removes ALL memories for this user"},
        ],
    }


def _consolidate() -> dict[str, Any]:
    return {
        "id": "consolidate", "label": "Consolidate", "icon": "🔄",
        "tool": "memory_memory_consolidate",
        "submit_label": "Consolidate",
        "fields": [
            {"name": "user_id", "label": "User ID", "type": "text",
             "placeholder": "default",
             "tooltip": "Promote short-term memories to long-term"},
        ],
    }
