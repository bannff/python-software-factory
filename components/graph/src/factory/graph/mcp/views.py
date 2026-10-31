"""Typed Graph dashboard helper tools and view definitions."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from ..runtime.runtime import GraphRuntime
from .dashboard_summary import build_dashboard_summary, get_entity_context
from .helper_models import DashboardSummaryData, EntityContextData, EntityContextInput, NoArgsInput, ViewsData
from .views_canvas import _action_pane, _entity_type_chart, _graph_viewer
from .views_entities import _entities_list, _neighborhood_stream


def register(mcp: Any, runtime: GraphRuntime) -> None:
    """Register typed Graph dashboard helpers."""

    @typed_tool(mcp)
    @deterministic(input_model=NoArgsInput, output_model=DashboardSummaryData)
    def graph_get_dashboard_summary() -> ToolResult[DashboardSummaryData]:
        """Return aggregate graph dashboard data."""
        return DashboardSummaryData(**build_dashboard_summary(runtime))

    @typed_tool(mcp)
    @deterministic(input_model=EntityContextInput, output_model=EntityContextData)
    def graph_get_entity_context(entity_id: str, limit: int = 12) -> ToolResult[EntityContextData]:
        """Return neighboring entities for a focus entity."""
        return EntityContextData(**get_entity_context(runtime, entity_id=entity_id, limit=limit))

    @typed_tool(mcp)
    @deterministic(input_model=NoArgsInput, output_model=ViewsData)
    def graph_get_views() -> ToolResult[ViewsData]:
        """Return Graph dashboard definitions as transport-agnostic data."""
        return ViewsData(views=[_dashboard()])


def _dashboard() -> dict:
    return {"id": "graph-dashboard", "name": "Graph", "brick": "graph", "icon": "🕸️",
            "layout": {"type": "flex", "direction": "column"},
            "components": [_entity_type_chart(), _entities_list(), _neighborhood_stream(),
                           _graph_viewer(), _action_pane()],
            "metadata": {"description": "Inspect correlated graph entities and neighborhoods",
                         "nav_label": "Graph", "nav_order": 35}}
