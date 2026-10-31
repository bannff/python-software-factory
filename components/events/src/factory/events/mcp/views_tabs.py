"""Tab and action builders for Events dashboard."""

from __future__ import annotations

from typing import Any



# ── Read-only tabs (lazy-loaded data) ──────────────────────────────


def events_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only event data."""
    return {
        "id": "events-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "history", "label": "Event History",
                 "lazy_tool": "events_list_history",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "live", "label": "Live Events",
                 "lazy_tool": "events_list_events",
                 "result_hints": {"searchable": True}},
                {"id": "subscriptions", "label": "Subscriptions",
                 "lazy_tool": "events_get_subscription_registry",
                 "result_hints": {"searchable": True}},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "events_health_check",
                 "result_hints": {"prefer": "stat_grid"}},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def events_actions() -> list[dict[str, Any]]:
    """Return action definitions for the events action pane."""
    return [
        _replay_event(),
        _get_event(),
        _upsert_subscription(),
        _delete_subscription(),
        _validate_subscriptions(),
    ]


def _replay_event() -> dict[str, Any]:
    return {
        "id": "replay-event", "label": "Replay Event", "icon": "🔁",
        "tool": "events_replay",
        "submit_label": "Replay",
        "fields": [
            {"name": "event_id", "label": "Event ID", "type": "text",
             "placeholder": "evt-abc123",
             "tooltip": "Re-publishes the event to all current subscribers"},
            {"name": "tenant_id", "label": "Tenant ID", "type": "text",
             "placeholder": "Optional tenant context",
             "tooltip": "Override tenant context for the replayed event"},
        ],
    }


def _get_event() -> dict[str, Any]:
    return {
        "id": "get-event", "label": "Lookup Event", "icon": "🔍",
        "tool": "events_get_event",
        "submit_label": "Lookup",
        "fields": [
            {"name": "event_id", "label": "Event ID", "type": "text",
             "placeholder": "evt-abc123",
             "tooltip": "Retrieve full event payload by its unique ID"},
        ],
    }


def _upsert_subscription() -> dict[str, Any]:
    return {
        "id": "save-subscription", "label": "Save Subscription", "icon": "📥",
        "tool": "events_authoring_upsert_subscription",
        "submit_label": "Save Subscription",
        "fields": [
            {"name": "subscription_id", "label": "Subscription ID",
             "type": "text", "placeholder": "my-handler-sub",
             "tooltip": "Unique identifier — updates if already exists"},
            {"name": "subscription_data", "label": "Definition (JSON)",
             "type": "textarea",
             "placeholder": '{"event_type": "user.*", "handler": "log"}',
             "tooltip": (
                 "JSON object with event_type, handler, description,"
                 " enabled, priority, and optional filters"
             )},
        ],
    }


def _delete_subscription() -> dict[str, Any]:
    return {
        "id": "delete-subscription",
        "label": "⚠ Delete Subscription", "icon": "🗑️",
        "tool": "events_authoring_delete_subscription",
        "submit_label": "Delete",
        "fields": [
            {"name": "subscription_id", "label": "Subscription ID",
             "type": "text", "placeholder": "my-handler-sub",
             "tooltip": "Permanently removes this subscription definition"},
        ],
    }


def _validate_subscriptions() -> dict[str, Any]:
    return {
        "id": "validate-subs", "label": "Validate Subscriptions",
        "icon": "✅",
        "tool": "events_authoring_validate_subscriptions",
        "submit_label": "Validate",
        "fields": [
            {"name": "dry_run", "label": "Mode", "type": "select",
             "options": [
                 {"value": "true", "label": "Dry Run (preview)"},
                 {"value": "false", "label": "Apply fixes"},
             ],
             "tooltip": "Dry run previews issues without making changes"},
        ],
    }
