"""Typed portable WorkflowRun listing tool."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .helper_models import RecentRunData, RecentRunsData, RecentRunsInput

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register typed WorkflowRun listing under its canonical name."""

    @typed_tool(mcp)
    @deterministic(input_model=RecentRunsInput, output_model=RecentRunsData)
    def graph_list_recent_runs(limit: int = 20, backend: str = "") -> ToolResult[RecentRunsData]:
        """Return recent WorkflowRun entities ordered by started_at descending."""
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return RecentRunsData(runs=[], count=0, error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        runs = graph.find_entities("WorkflowRun", None, limit)
        recent = sorted(runs, key=lambda item: item.properties.get("started_at", ""), reverse=True)[:limit]
        data = [RecentRunData(id=item.id, run_id=str(item.properties.get("run_id", "")),
                              status=str(item.properties.get("status", "unknown")),
                              started_at=str(item.properties.get("started_at", ""))) for item in recent]
        return RecentRunsData(runs=data, count=len(data))
