"""Tab and action builders for Cache dashboard.

Exports:
- cache_read_tabs(): read-only tabs (browse, stats, health)
- cache_actions(): write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def cache_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only cache data."""
    return {
        "id": "cache-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "browse", "label": "Browse Keys",
                 "lazy_tool": "cache_cache_keys"},
                {"id": "stats", "label": "Statistics",
                 "lazy_tool": "cache_cache_stats"},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "cache_health_check"},
            ],
        },
    }


def cache_actions() -> list[dict[str, Any]]:
    """Return action definitions for the cache action pane."""
    return [
        _set_value(), _delete_key(),
        _check_exists(), _check_ttl(), _clear_cache(),
    ]


def _set_value() -> dict[str, Any]:
    return {
        "id": "set-value", "label": "Set Value", "icon": "💾",
        "tool": "cache_cache_set",
        "submit_label": "Set Value",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "namespace:key",
             "tooltip": "Cache key — use colon-separated namespaces"},
            {"name": "value", "label": "Value", "type": "textarea",
             "placeholder": "Value to cache (string)",
             "tooltip": "String value to store"},
            {"name": "ttl_seconds", "label": "TTL (seconds)",
             "type": "number", "placeholder": "3600",
             "tooltip": "Time-to-live — leave empty for no expiry"},
        ],
    }


def _delete_key() -> dict[str, Any]:
    return {
        "id": "delete-key", "label": "Delete Key", "icon": "🗑️",
        "tool": "cache_cache_delete",
        "submit_label": "Delete",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "namespace:key",
             "tooltip": "Exact key to remove from cache"},
        ],
    }


def _check_exists() -> dict[str, Any]:
    return {
        "id": "check-exists", "label": "Key Exists?", "icon": "❓",
        "tool": "cache_cache_exists",
        "submit_label": "Check Exists",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "namespace:key",
             "tooltip": "Check whether a key exists and is not expired"},
        ],
    }


def _check_ttl() -> dict[str, Any]:
    return {
        "id": "check-ttl", "label": "Check TTL", "icon": "⏱️",
        "tool": "cache_cache_ttl",
        "submit_label": "Check TTL",
        "fields": [
            {"name": "key", "label": "Key", "type": "text",
             "placeholder": "namespace:key",
             "tooltip": "Check remaining time-to-live for a key"},
        ],
    }


def _clear_cache() -> dict[str, Any]:
    return {
        "id": "clear-cache", "label": "⚠ Clear Cache", "icon": "⚠️",
        "tool": "cache_cache_clear",
        "submit_label": "Clear Cache",
        "fields": [],
    }
