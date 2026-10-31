"""Canonical typed Graph run/evidence MCP reads."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from ._deterministic_typed_helpers import coerce_edges, coerce_labels, resolve_target_app
from .evidence_models import (
    CountsData, CountsInput, FindingsInput, LimitInput, RecentFindingsInput, RowsData,
    RunLimitInput, SummaryData, SummaryInput, TargetAppData, TargetAppInput,
    TopologyData, TopologyInput,
)
from ..runtime.topology_errors import GraphTopologyUnsupportedError

if TYPE_CHECKING:
    from ..runtime.ports import Entity, Relationship
    from ..runtime.runtime import GraphRuntime


def _topology_entity(entity: "Entity") -> dict:
    return {
        "id": entity.id, "type": entity.type,
        "properties": entity.properties, "labels": entity.labels,
    }


def _topology_relationship(relationship: "Relationship") -> dict:
    return {
        "id": relationship.id, "type": relationship.type,
        "source": relationship.source_id, "target": relationship.target_id,
        "properties": relationship.properties,
    }


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register typed portable evidence reads under their canonical names."""

    @typed_tool(mcp)
    @deterministic(input_model=TopologyInput, output_model=TopologyData)
    def graph_get_run_topology(run_id: str, limit: int = 200, backend: str = "") -> ToolResult[TopologyData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return TopologyData(run_id=run_id, nodes=[], edges=[], node_count=0, edge_count=0,
                                error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        try:
            result = graph.get_run_topology(run_id, limit)
        except GraphTopologyUnsupportedError as exc:
            return ToolResult(ok=False, error=exc.code)
        nodes = [_topology_entity(entity) for entity in result.entities]
        edges = [_topology_relationship(relationship) for relationship in result.relationships]
        return TopologyData(
            run_id=run_id, nodes=nodes, edges=edges,
            node_count=len(nodes), edge_count=len(edges),
        )

    @typed_tool(mcp)
    @deterministic(input_model=FindingsInput, output_model=RowsData)
    def graph_get_findings_for_run(run_id: str, app: str = "", limit: int = 50,
                                   taxonomy_edges: list[dict] | None = None,
                                   backend: str = "") -> ToolResult[RowsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return RowsData(rows=[], count=0, error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        rows = list(graph.get_findings_for_run(
            run_id, app, limit, taxonomy_edges=coerce_edges(taxonomy_edges)).raw or [])
        return RowsData(rows=rows, count=len(rows))

    @typed_tool(mcp)
    @deterministic(input_model=CountsInput, output_model=CountsData)
    def graph_count_entities_by_run(run_id: str, labels: list[str] | str | None = None,
                                    backend: str = "") -> ToolResult[CountsData]:
        chosen = coerce_labels(labels)
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return CountsData(run_id=run_id, labels=chosen, counts={}, total=0,
                              error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        counts = graph.count_entities_by_run(run_id, chosen)
        return CountsData(run_id=run_id, labels=chosen, counts=counts,
                          total=sum(int(value) for value in counts.values()))

    @typed_tool(mcp)
    @deterministic(input_model=SummaryInput, output_model=SummaryData)
    def graph_get_workflow_summary(run_id: str, taxonomy_edges: list[dict] | None = None,
                                   count_labels: list[str] | str | None = None,
                                   backend: str = "") -> ToolResult[SummaryData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return SummaryData(run={}, suspected_count=0, finding_count=0, finding_verdicts={},
                               exploit_count=0, endpoints_discovered=0, target_app="",
                               error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        labels = coerce_labels(count_labels)
        counts = graph.count_entities_by_run(run_id, labels)
        run = graph.get_entity(f"workflow-run-{run_id}")
        rows = list(graph.get_findings_for_run(
            run_id, "", 1000, taxonomy_edges=coerce_edges(taxonomy_edges)).raw or [])
        verdicts: dict[str, int] = {}
        for row in rows:
            verdict = str(row.get("verdict") or "unknown")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
        endpoints = graph.find_entities("EndpointInventory", {"run_id": run_id}, 1)
        return SummaryData(run={"run_id": run_id, **(run.properties if run else {})},
                           suspected_count=int(counts.get("SuspectedVuln", 0)),
                           finding_count=int(counts.get("Finding", 0)),
                           finding_verdicts=verdicts,
                           exploit_count=int(counts.get("ProvenExploit", 0)),
                           endpoints_discovered=int(endpoints[0].properties.get("count", 0)) if endpoints else 0,
                           target_app=resolve_target_app(graph, run_id))

    @typed_tool(mcp)
    @deterministic(input_model=RecentFindingsInput, output_model=RowsData)
    def graph_get_recent_findings(severity: str = "", app: str = "", run_id: str = "",
                                 limit: int = 50, taxonomy_edges: list[dict] | None = None,
                                 backend: str = "") -> ToolResult[RowsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return RowsData(rows=[], count=0, error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        rows = list(graph.get_recent_findings(
            severity, app, run_id, limit, taxonomy_edges=coerce_edges(taxonomy_edges)).raw or [])
        return RowsData(rows=rows, count=len(rows))

    @typed_tool(mcp)
    @deterministic(input_model=TargetAppInput, output_model=TargetAppData)
    def graph_get_target_app(target_app: str, run_id: str = "", backend: str = "") -> ToolResult[TargetAppData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return TargetAppData(found=False, target_app=target_app, run_id=run_id,
                                 error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        entity = graph.get_target_app(target_app, run_id)
        data = None if entity is None else {"id": entity.id, "type": entity.type,
                                            "properties": entity.properties,
                                            "labels": entity.labels}
        return TargetAppData(found=entity is not None, target_app=target_app,
                             run_id=run_id, entity=data)

    @typed_tool(mcp)
    @deterministic(input_model=RunLimitInput, output_model=RowsData)
    def graph_get_tool_invocations_for_run(run_id: str, limit: int = 50,
                                           backend: str = "") -> ToolResult[RowsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return RowsData(rows=[], count=0, error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        rows = list(graph.get_tool_invocations_for_run(run_id, limit).raw or [])
        return RowsData(rows=rows, count=len(rows))

    @typed_tool(mcp)
    @deterministic(input_model=LimitInput, output_model=RowsData)
    def graph_list_recent_tool_invocations(limit: int = 100,
                                           backend: str = "") -> ToolResult[RowsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return RowsData(rows=[], count=0, error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        rows = list(graph.list_recent_tool_invocations(limit).raw or [])
        return RowsData(rows=rows, count=len(rows))
