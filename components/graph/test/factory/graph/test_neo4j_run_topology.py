"""Neo4j uses native bounded Cypher with NetworkX-equivalent selection."""
from __future__ import annotations

import pytest

from factory.graph.runtime.adapters.aws import NeptuneGraphAdapter
from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.topology_errors import GraphTopologyUnsupportedError


class _Session:
    def __init__(self, calls: list[tuple[str, dict]]) -> None:
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query: str, **params):
        self.calls.append((query, params))
        if "MATCH (n)" in query:
            return [{
                "id": "run-a", "type": "WorkflowRun", "labels": ["WorkflowRun"],
                "properties": {"run_id": "a"},
            }]
        if "a.id IN $seed_ids" in query:
            return [
                _edge_row("incident", "run-a", "shared", {}),
                _edge_row("foreign", "run-a", "run-b", {"run_id": "b"}),
            ]
        return [_edge_row(
            "observed", "telemetry-a", "agent-a",
            {"browse_metadata": {"run_id": "a"}},
        )]


class _Driver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def session(self, **_kwargs):
        return _Session(self.calls)


def _edge_row(edge_id: str, source: str, target: str, properties: dict) -> dict:
    return {
        "id": edge_id, "type": "OBSERVED", "source_id": source,
        "target_id": target, "properties": properties,
        "source_type": "Node", "source_labels": ["Node"],
        "source_properties": {}, "target_type": "Node",
        "target_labels": ["Node"], "target_properties": {},
    }


def test_neo4j_topology_uses_native_queries_and_exact_selection() -> None:
    driver = _Driver()
    graph = Neo4jGraph()
    graph._driver = driver
    result = graph.get_run_topology("a", 10)

    assert [entity.id for entity in result.entities] == [
        "run-a", "agent-a", "shared", "telemetry-a",
    ]
    assert [relationship.id for relationship in result.relationships] == [
        "incident", "observed",
    ]
    assert len(driver.calls) == 3
    assert all("LIMIT" in query and "ORDER BY" in query for query, _ in driver.calls)
    assert driver.calls[0][1]["seed_limit"] == 10
    assert driver.calls[1][1]["candidate_limit"] == 20


def test_advertised_neptune_topology_fails_with_capability_error() -> None:
    graph = object.__new__(NeptuneGraphAdapter)
    with pytest.raises(GraphTopologyUnsupportedError, match="neptune"):
        graph.get_run_topology("run", 10)
