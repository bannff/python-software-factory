"""Typed Events dashboard views."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, make_serializable

from .contracts.base import EmptyInput
from .contracts.views import (
    DashboardSummaryOutput, EventGraphContextInput, EventGraphContextOutput,
    HistoryEntryInput, HistoryEntryOutput, ViewsOutput,
)
from ..runtime.runtime import EventsRuntime
from .dashboard_summary import build_dashboard_summary, get_history_entry, list_related_graph_entities
from .views_components import _children


def register(mcp: Any, runtime: EventsRuntime) -> None:
    """Register Events dashboard tools with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardSummaryOutput)
    def events_get_dashboard_summary() -> ToolResult[DashboardSummaryOutput]:
        return make_serializable(build_dashboard_summary(runtime))

    @mcp.tool()
    @deterministic(input_model=HistoryEntryInput, output_model=HistoryEntryOutput)
    def events_get_event_history_entry(event_id: str) -> ToolResult[HistoryEntryOutput]:
        result = get_history_entry(runtime, event_id)
        return make_serializable({"event_id": event_id, **result})

    @mcp.tool()
    @deterministic(input_model=EventGraphContextInput, output_model=EventGraphContextOutput)
    def events_get_event_graph_context(event_id: str, limit: int = 12) -> ToolResult[EventGraphContextOutput]:
        entries = list_related_graph_entities(event_id=event_id, limit=limit,
                                              rows=build_dashboard_summary(runtime).get("events", []))
        return make_serializable({"event_id": event_id, "entries": entries, "count": len(entries)})

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def events_get_views() -> ToolResult[ViewsOutput]:
        return make_serializable({"views": [{"id": "events-stream", "name": "Event Stream", "brick": "events",
            "icon": "⚡", "layout": {"type": "flex", "direction": "column"},
            "components": _children(), "metadata": {"description": "Publish and browse events",
            "nav_label": "Events", "nav_order": 20}}]})
