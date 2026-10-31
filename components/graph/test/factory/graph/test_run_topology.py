"""Exact bounded run-topology behavior for persisted Graph records."""
from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from factory.graph.mcp.evidence_models import TopologyInput
from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity, Relationship
from factory.graph.runtime.provenance_models import GraphRelationshipWrite
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server


def _entity(graph: NetworkXGraph, entity_id: str, run_id: str | None = None, kind: str = "Node") -> None:
    properties = {} if run_id is None else {"run_id": run_id}
    graph.add_entity(Entity(id=entity_id, type=kind, properties=properties))


def _edge(
    graph: NetworkXGraph, relationship_id: str, source: str, target: str,
    properties: dict | None = None,
) -> None:
    graph.add_relationship(Relationship(
        id=relationship_id, type="LINKS", source_id=source,
        target_id=target, properties=properties or {},
    ))


def test_topology_isolates_shared_boundary_and_includes_disconnected_evidence() -> None:
    graph = NetworkXGraph()
    for entity_id, run_id, kind in (
        ("run-a", "a", "WorkflowRun"), ("run-b", "b", "WorkflowRun"),
        ("eval-a", "a", "EvaluationRef"), ("metric-a", "a", "MeasurementRef"),
        ("shared", None, "ArtifactRef"), ("foreign-b", "b", "ArtifactRef"),
    ):
        _entity(graph, entity_id, run_id, kind)
    _edge(graph, "edge-a", "run-a", "shared", {"ordinal": 1})
    _edge(graph, "edge-b", "run-b", "shared", {"ordinal": 2})
    _edge(graph, "foreign-edge", "run-a", "foreign-b", {"run_id": "b"})
    observed = GraphRelationshipWrite(
        source_system="telemetry", source_identity="span-a", source_digest="digest",
        relation_type="OBSERVED", source_endpoint="telemetry-a", target_endpoint="agent-a",
        source_ref="ref-a", visibility="private",
        browse_metadata={"run_id": "a", "signal": "span"},
    )
    observed_result = graph.write_relationship(observed)

    result = graph.get_run_topology("a", 20)
    node_ids = [entity.id for entity in result.entities]
    edge_ids = [relationship.id for relationship in result.relationships]
    assert node_ids[:3] == ["eval-a", "metric-a", "run-a"]
    assert {"shared", "telemetry-a", "agent-a"} <= set(node_ids)
    assert {"run-b", "foreign-b"}.isdisjoint(node_ids)
    assert edge_ids == sorted(edge_ids)
    assert {"edge-a", observed_result.relationship_id} == set(edge_ids)
    assert "edge-b" not in edge_ids and "foreign-edge" not in edge_ids
    assert all(rel.type != "NEXT_IN_RUN" for rel in result.relationships)
    assert all({rel.source_id, rel.target_id} <= set(node_ids) for rel in result.relationships)


def test_topology_caps_and_order_are_deterministic_without_dangling_endpoints() -> None:
    graph = NetworkXGraph()
    for entity_id in ("seed-3", "seed-1", "seed-2", "seed-0"):
        _entity(graph, entity_id, "run")
    for entity_id in ("boundary-2", "boundary-0", "boundary-1"):
        _entity(graph, entity_id)
    _edge(graph, "rel-c", "seed-1", "boundary-2")
    _edge(graph, "rel-a", "seed-0", "boundary-0")
    _edge(graph, "rel-b", "seed-0", "boundary-1")

    first = graph.get_run_topology("run", 2)
    second = graph.get_run_topology("run", 2)
    assert [entity.id for entity in first.entities] == [
        "seed-0", "seed-1", "boundary-0", "boundary-1",
    ]
    assert [rel.id for rel in first.relationships] == ["rel-a", "rel-b"]
    assert first == second
    node_ids = {entity.id for entity in first.entities}
    assert all({rel.source_id, rel.target_id} <= node_ids for rel in first.relationships)


def test_mcp_serializes_persisted_relationship_identity_and_properties() -> None:
    runtime = GraphRuntime({"default_backend": "networkx"})
    graph = runtime.get_graph("networkx")
    _entity(graph, "run", "r", "WorkflowRun")
    _entity(graph, "boundary")
    graph.add_entity(Entity(
        id="invocation-1", type="ToolInvocation",
        properties={"workflow_run_id": "r", "sequence": 1},
    ))
    graph.add_entity(Entity(
        id="invocation-2", type="ToolInvocation",
        properties={"workflow_run_id": "r", "sequence": 2},
    ))
    _edge(graph, "persisted-edge", "run", "boundary", {"ordinal": 7})
    server = create_mcp_server(runtime)
    tool = asyncio.run(server.get_tool("graph_get_run_topology"))
    result = tool.fn(run_id="r", limit=10)
    assert result.ok and result.data is not None
    assert result.data.edges == [{
        "id": "persisted-edge", "type": "LINKS", "source": "run",
        "target": "boundary", "properties": {"ordinal": 7},
    }]


@pytest.mark.parametrize("payload", [
    {"run_id": ""}, {"run_id": "   "}, {"run_id": "r", "limit": 0},
    {"run_id": "r", "limit": 201}, {"run_id": "r", "limit": "2"},
])
def test_topology_input_is_strict_and_bounded(payload: dict) -> None:
    with pytest.raises(ValidationError):
        TopologyInput.model_validate(payload)
