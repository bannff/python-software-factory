"""MCP Resource registration for Events brick.

Resources expose static/queryable data:
- Schemas for events and subscriptions
- Documentation on event types and patterns
- Live subscription registry
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

from .docs import EVENTS_DOCS

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import EventsRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "EventsRuntime"],
    get_config_dir: Callable[[], "Path"],
) -> None:
    """Register all Events resources with the MCP server."""
    from ..runtime.models import Event, EventFilter
    from ..runtime.subscriptions import SubscriptionDefinition
    from ..runtime.history import EventHistoryEntry
    from ..runtime.learning_contracts import learning_event_schemas

    # Schema resources
    @mcp.resource("events://schemas/event")
    def resource_event_schema() -> str:
        """Get the JSON schema for events."""
        return json.dumps(Event.model_json_schema(), indent=2)

    @mcp.resource("events://schemas/subscription")
    def resource_subscription_schema() -> str:
        """Get the JSON schema for subscriptions."""
        return json.dumps(SubscriptionDefinition.model_json_schema(), indent=2)

    @mcp.resource("events://schemas/filter")
    def resource_filter_schema() -> str:
        """Get the JSON schema for event filters."""
        return json.dumps(EventFilter.model_json_schema(), indent=2)

    @mcp.resource("events://schemas/history")
    def resource_history_schema() -> str:
        """Get the JSON schema for history entries."""
        return json.dumps(EventHistoryEntry.model_json_schema(), indent=2)

    @mcp.resource("events://schemas/learning")
    def resource_learning_schemas() -> str:
        """Get JSON schemas for canonical learning events."""
        return json.dumps(learning_event_schemas(), indent=2)

    # Documentation resources
    @mcp.resource("events://docs")
    def resource_docs_list() -> str:
        """List available events documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in EVENTS_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("events://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get events documentation by name."""
        if doc_name in EVENTS_DOCS:
            return EVENTS_DOCS[doc_name]["content"]
        available = list(EVENTS_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    # Live data resources
    @mcp.resource("events://subscriptions")
    def resource_subscriptions() -> str:
        """List all registered subscriptions."""
        runtime = get_runtime()
        registry = runtime.get_subscription_registry()
        subs = registry.list_all()
        return json.dumps({
            "subscriptions": [
                {"id": s.id, "event_type": s.event_type, "handler": s.handler,
                 "enabled": s.enabled, "priority": s.priority}
                for s in subs
            ],
            "count": len(subs),
        }, indent=2)

    @mcp.resource("events://subscriptions/{subscription_id}")
    def resource_subscription(subscription_id: str) -> str:
        """Get a specific subscription by ID."""
        runtime = get_runtime()
        registry = runtime.get_subscription_registry()
        sub = registry.get(subscription_id)
        if sub is None:
            return json.dumps({"error": f"Subscription not found: {subscription_id}"})
        return json.dumps({
            "id": sub.id, "event_type": sub.event_type, "handler": sub.handler,
            "description": sub.description, "enabled": sub.enabled,
            "priority": sub.priority, "filters": sub.filters,
        }, indent=2)

    @mcp.resource("events://events/{event_id}")
    def resource_event(event_id: str) -> str:
        """Get a specific event by ID."""
        runtime = get_runtime()
        event = runtime.get_event(event_id)
        if event is None:
            return json.dumps({"error": f"Event not found: {event_id}"})
        return json.dumps({
            "id": event.id, "type": event.type, "source": event.source,
            "payload": event.payload, "timestamp": event.timestamp.isoformat(),
        }, indent=2)

    @mcp.resource("events://history/{event_id}")
    def resource_history_entry(event_id: str) -> str:
        """Get a specific event history entry by event ID."""
        runtime = get_runtime()
        entries = runtime.list_event_history(limit=1000)
        entry = next((entry for entry in entries if entry.event_id == event_id), None)
        if entry is None:
            return json.dumps({"error": f"History entry not found: {event_id}"})
        return json.dumps({
            "event_id": entry.event_id,
            "event_type": entry.event_type,
            "source": entry.source,
            "payload": entry.payload,
            "timestamp": entry.timestamp.isoformat(),
            "tenant_id": entry.tenant_id,
            "principal_id": entry.principal_id,
            "correlation_id": entry.correlation_id,
            "metadata": entry.metadata,
        }, indent=2)

    # Cross-reference to factory
    @mcp.resource("events://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"],
            "related_bricks": {
                "workflow": "Uses events for wait_for_event steps",
                "notification": "Subscribes to events for alerts",
            },
        }, indent=2)
