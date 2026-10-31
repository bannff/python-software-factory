from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.ports import Entity


def _graph_with_driver() -> tuple[Neo4jGraph, MagicMock, MagicMock]:
    graph = Neo4jGraph()
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    graph._driver = driver
    graph.get_entity = lambda entity_id: Entity(entity_id, "Node")
    return graph, driver, session


def test_neo4j_neighbors_bounds_query_and_result() -> None:
    graph, _driver, session = _graph_with_driver()
    session.run.return_value = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]

    neighbors = graph.get_neighbors("source", limit=2)

    assert [entity.id for entity in neighbors] == ["n1", "n2"]
    query = session.run.call_args.args[0]
    assert "DISTINCT" in query
    assert "ORDER BY id" in query
    assert "LIMIT $limit" in query
    assert session.run.call_args.kwargs["limit"] == 2


def test_neo4j_neighbors_rejects_invalid_limit() -> None:
    graph, driver, _session = _graph_with_driver()

    with pytest.raises(ValueError, match="neighbor limit"):
        graph.get_neighbors("source", limit=0)

    driver.session.assert_not_called()
