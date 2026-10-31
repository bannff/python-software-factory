"""Typed deterministic MCP tools for Events."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, make_serializable

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, HealthOutput, QueryEventsInput,
    QueryEventsOutput, SubscriptionRegistryOutput,
)
from ..runtime.envelope import ContextEnvelope
from ..runtime.history import EventHistoryEntry
from ..runtime.models import Event
from ..runtime.subscriptions import SubscriptionDefinition

if TYPE_CHECKING:
    from pathlib import Path
    from ..authoring import EventsAuthoring
    from ..runtime.runtime import EventsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"],
             get_authoring: Callable[[], "EventsAuthoring"],
             get_config_dir: Callable[[], "Path"]) -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def events_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        authoring = get_authoring()
        return {"version": "0.1.0", "authoring_enabled": authoring.is_enabled(),
                "config_dir": str(get_config_dir()), "features": {"event_publishing": True,
                "subscriptions": True, "event_history": True, "event_replay": True,
                "pattern_matching": True}}

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def events_health_check() -> ToolResult[HealthOutput]:
        try:
            runtime = get_runtime()
            subscriptions = runtime.get_subscription_registry().list_all()
            return {"status": "healthy", "subscriptions_loaded": len(subscriptions),
                    "history_retention_days": runtime.get_history_retention_days(),
                    "config_dir": str(get_config_dir())}
        except Exception as error:
            return {"status": "unhealthy", "error": str(error),
                    "config_dir": str(get_config_dir())}

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def events_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        from ..runtime.learning_contracts import learning_event_schemas
        return make_serializable({"event_schema": Event.model_json_schema(),
            "subscription_schema": SubscriptionDefinition.model_json_schema(),
            "envelope_schema": ContextEnvelope.model_json_schema(),
            "history_entry_schema": EventHistoryEntry.model_json_schema(),
            "history_retention": {"type": "object", "properties": {
                "event_store.retention_days": {"type": "integer", "minimum": 1,
                "description": "Optional retention window in days for durable event history when using persistent backends."}}},
            "learning_event_schemas": learning_event_schemas()})

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=SubscriptionRegistryOutput)
    def events_get_subscription_registry() -> ToolResult[SubscriptionRegistryOutput]:
        subscriptions = get_runtime().get_subscription_registry().list_all()
        rows = [{"id": item.id, "event_type": item.event_type, "handler": item.handler,
                 "description": item.description, "enabled": item.enabled,
                 "priority": item.priority, "has_filters": bool(item.filters)}
                for item in subscriptions]
        return {"subscriptions": rows, "total": len(rows)}

    @mcp.tool()
    @deterministic(input_model=QueryEventsInput, output_model=QueryEventsOutput)
    def events_query_events(event_type: str | None = None, source: str | None = None,
                            payload_key: str | None = None, payload_value: str | None = None,
                            limit: int = 100) -> ToolResult[QueryEventsOutput]:
        events = get_runtime().list_events(event_type=event_type, source=source, limit=limit)
        rows = [{"id": event.id, "type": event.type, "payload": event.payload,
                 "source": event.source, "timestamp": event.timestamp.isoformat(),
                 "trace_id": event.trace_id, "session_id": event.session_id,
                 "principal_id": event.principal_id} for event in events]
        if payload_key is not None:
            rows = [row for row in rows if str(row["payload"].get(payload_key)) == str(payload_value)]
        return {"events": make_serializable(rows), "total": len(rows)}
