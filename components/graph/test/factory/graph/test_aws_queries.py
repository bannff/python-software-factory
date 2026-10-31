"""Tests for portable Neptune traversal, search, and health."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.graph.runtime.ports import Entity, GraphHealth, GraphPath


@pytest.fixture
def adapter():
    """Create NeptuneGraphAdapter with mocked urllib."""
    with patch("boto3.resource"), patch("boto3.client"):
        from factory.graph.runtime.adapters.aws import NeptuneGraphAdapter

        return NeptuneGraphAdapter(endpoint="test", port=8182)


def _mock_query(adapter, return_value: dict) -> MagicMock:
    """Patch _query to return a canned response."""
    mock = MagicMock(return_value=return_value)
    adapter._query = mock
    adapter._rows = lambda q, p=None: mock(q, p).get("results", [])
    return mock


class TestGetNeighbors:
    """get_neighbors() traversal tests."""

    def test_neighbors_both_directions(self, adapter) -> None:
        """Default direction='both' returns neighbors."""
        mock = _mock_query(adapter, {
            "results": [
                {"b": {"id": "n1", "type": "Person"}},
                {"b": {"id": "n2", "type": "Place"}},
            ],
        })
        neighbors = adapter.get_neighbors("e1", limit=1)
        assert len(neighbors) == 1
        assert all(isinstance(n, Entity) for n in neighbors)
        assert "LIMIT $limit" in mock.call_args.args[0]
        assert mock.call_args.args[1]["limit"] == 1

    def test_neighbors_outgoing(self, adapter) -> None:
        """direction='out' queries outgoing edges."""
        _mock_query(adapter, {"results": [{"b": {"id": "n1", "type": "X"}}]})
        neighbors = adapter.get_neighbors("e1", direction="out")
        assert len(neighbors) == 1

    def test_neighbors_incoming(self, adapter) -> None:
        """direction='in' queries incoming edges."""
        _mock_query(adapter, {"results": []})
        neighbors = adapter.get_neighbors("e1", direction="in")
        assert neighbors == []

    def test_neighbors_with_rel_type(self, adapter) -> None:
        """Filters by relationship_type."""
        _mock_query(adapter, {"results": [{"b": {"id": "n1", "type": "X"}}]})
        neighbors = adapter.get_neighbors("e1", relationship_type="KNOWS")
        assert len(neighbors) == 1


class TestFindPath:
    """find_path() shortest path tests."""

    def test_find_path_found(self, adapter) -> None:
        """Returns GraphPath when path exists."""
        _mock_query(adapter, {"results": [{"p": {}}]})
        path = adapter.find_path("a", "b")
        assert isinstance(path, GraphPath)

    def test_find_path_not_found(self, adapter) -> None:
        """Returns None when no path exists."""
        _mock_query(adapter, {"results": []})
        assert adapter.find_path("a", "z") is None


class TestFindEntities:
    """find_entities() search tests."""

    def test_find_all(self, adapter) -> None:
        """Returns entities without type filter."""
        _mock_query(adapter, {
            "results": [{"n": {"id": "e1", "type": "X"}}],
        })
        entities = adapter.find_entities()
        assert len(entities) == 1

    def test_find_by_type(self, adapter) -> None:
        """Filters by entity_type."""
        _mock_query(adapter, {
            "results": [{"n": {"id": "e1", "type": "Person"}}],
        })
        entities = adapter.find_entities(entity_type="Person")
        assert len(entities) == 1
        assert entities[0].type == "Person"


class TestHealthAndInfrastructure:
    def test_health_check_healthy(self, adapter) -> None:
        """Healthy when count query succeeds."""
        _mock_query(adapter, {"results": [{"cnt": 42}]})
        h = adapter.health_check()
        assert isinstance(h, GraphHealth)
        assert h.healthy is True
        assert h.backend == "neptune"
        assert h.node_count == 42

    def test_health_check_failure(self, adapter) -> None:
        """Unhealthy when query raises."""
        adapter._query = MagicMock(side_effect=Exception("timeout"))
        adapter._rows = adapter._query
        h = adapter.health_check()
        assert h.healthy is False
        assert "timeout" in h.message

    def test_infrastructure_spec(self, adapter) -> None:
        """Returns valid Neptune spec dict."""
        spec = adapter.infrastructure_spec()
        assert spec["service"] == "neptune"
        assert spec["construct"] == "DatabaseCluster"
        assert "serverless_scaling" in spec["props"]
