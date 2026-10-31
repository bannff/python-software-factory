"""Neo4j parity tests for authority-scoped neighborhoods."""
from __future__ import annotations

from unittest.mock import MagicMock

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.neighborhood import NeighborhoodRequest, encode_node_id
from factory.graph.runtime.ports import Entity

TENANT, OWNER = "tenant-a", "owner-a"


def _id(index: int, owner: str = OWNER) -> str:
    return encode_node_id("lesson", TENANT, owner, f"node-{index}")


def _row(source: str, target: str, edge_id: str = "edge") -> dict:
    return {
        "id": edge_id, "type": "LINKS", "source_id": source,
        "target_id": target, "properties": {"ordinal": 1},
        "source_type": "Lesson", "source_labels": ["Lesson"],
        "source_properties": {"id": source},
        "target_type": "Lesson", "target_labels": ["Lesson"],
        "target_properties": {"id": target},
    }


def _adapter(rows: list[dict]) -> tuple[Neo4jGraph, MagicMock]:
    adapter = Neo4jGraph()
    driver, session = MagicMock(), MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    session.run.return_value = rows
    adapter._driver = driver
    adapter.get_entity = lambda value: Entity(value, "Lesson")
    return adapter, session


def test_neo4j_neighborhood_is_parameterized_and_returns_edges() -> None:
    adapter, session = _adapter([_row(_id(0), _id(1))])
    result = adapter.get_neighborhood(NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, ("LINKS",), "out", 1, 10, 10,
    ))
    assert [entity.id for entity in result.entities] == [_id(0), _id(1)]
    assert [edge.id for edge in result.relationships] == ["edge"]
    query = session.run.call_args.args[0]
    assert "$tenant" in query and "$principal" in query and "$types" in query
    assert "LIMIT $limit" in query
    assert session.run.call_args.kwargs["frontier"] == [_id(0)]
    assert session.run.call_args.kwargs["types"] == ["LINKS"]


def test_neo4j_neighborhood_drops_foreign_rows_defense_in_depth() -> None:
    foreign = _id(9, "owner-b")
    adapter, _session = _adapter([_row(_id(0), foreign, "foreign")])
    result = adapter.get_neighborhood(NeighborhoodRequest(
        (_id(0),), TENANT, OWNER, max_depth=2,
    ))
    assert [entity.id for entity in result.entities] == [_id(0)]
    assert result.relationships == ()
