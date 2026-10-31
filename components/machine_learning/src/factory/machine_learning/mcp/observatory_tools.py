"""Thin deterministic MCP surface for the ML Observatory."""
from __future__ import annotations

from typing import Any, Callable
from factory.mcp_utils.interface import ToolResult, deterministic, fail
from ..runtime.observatory_lineage import build_lineage
from ..runtime.observatory_projection import build_summary
from ..runtime.observatory_sources import collect_sources
from .observatory_dtos import EmptyInput, ObservatoryLineageOutput, ObservatorySummaryOutput


def register(mcp: Any, runtime_supplier: Callable[[], Any]) -> None:
    """Register source-aware Observatory projections."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ObservatorySummaryOutput)
    def ml_get_observatory_summary() -> ToolResult[ObservatorySummaryOutput]:
        """Return honest training, learning, model, and progress populations."""
        try:
            return ObservatorySummaryOutput(**build_summary(collect_sources(runtime_supplier)))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ObservatoryLineageOutput)
    def ml_get_observatory_lineage() -> ToolResult[ObservatoryLineageOutput]:
        """Return bounded evidence-only lineage without graph-tool calls."""
        try:
            sources = collect_sources(runtime_supplier)
            by_name = {source["name"]: source.get("value") for source in sources}
            lineage = build_lineage(by_name.get("training_receipts") or [], by_name.get("learning_runs") or [])
            lineage["sources"] = [{key: value for key, value in source.items() if key != "value"} for source in sources]
            return ObservatoryLineageOutput(**lineage)
        except Exception as exc:
            return fail(str(exc))


__all__ = ["register"]
