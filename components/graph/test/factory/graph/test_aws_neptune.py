"""Tests for Neptune graph adapter — entity/relationship CRUD.

All HTTP calls to Neptune are mocked — no real AWS resources needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from factory.graph.runtime.ports import Entity, GraphHealth, Relationship


@pytest.fixture
def adapter():
    """Create NeptuneGraphAdapter with mocked urllib."""
    with patch("boto3.resource"), patch("boto3.client"):
        from factory.graph.runtime.adapters.aws import NeptuneGraphAdapter

        return NeptuneGraphAdapter(
            endpoint="test-neptune", port=8182, region="us-east-1",
        )


def _mock_query(adapter, return_value: dict) -> MagicMock:
    """Patch _query to return a canned response."""
    mock = MagicMock(return_value=return_value)
    adapter._query = mock
    adapter._rows = lambda q, p=None: mock(q, p).get("results", [])
    return mock


class TestNeptuneEntityCRUD:
    """Entity add/get/update/delete."""

    def test_add_entity(self, adapter) -> None:
        """add_entity() sends CREATE query and returns entity with id."""
        _mock_query(adapter, {"results": [{"n": {}}]})
        entity = Entity(id="e1", type="Person", properties={"name": "Alice"})
        result = adapter.add_entity(entity)
        assert result.id == "e1"
        assert result.type == "Person"

    def test_add_entity_generates_id(self, adapter) -> None:
        """add_entity() generates UUID when id is empty."""
        _mock_query(adapter, {"results": [{"n": {}}]})
        entity = Entity(id="", type="Thing", properties={})
        result = adapter.add_entity(entity)
        assert result.id != ""

    def test_get_entity_found(self, adapter) -> None:
        """get_entity() returns Entity when found."""
        _mock_query(adapter, {
            "results": [{"n": {"id": "e1", "type": "Person", "name": "Bob"}}],
        })
        result = adapter.get_entity("e1")
        assert result is not None
        assert result.type == "Person"
        assert "name" in result.properties

    def test_get_entity_not_found(self, adapter) -> None:
        """get_entity() returns None when not found."""
        _mock_query(adapter, {"results": []})
        assert adapter.get_entity("missing") is None

    def test_update_entity(self, adapter) -> None:
        """update_entity() sends SET query and returns entity."""
        _mock_query(adapter, {"results": [{"n": {}}]})
        entity = Entity(id="e1", type="Person", properties={"age": 30})
        result = adapter.update_entity(entity)
        assert result.id == "e1"

    def test_delete_entity(self, adapter) -> None:
        """delete_entity() sends DETACH DELETE and returns True."""
        _mock_query(adapter, {"results": []})
        assert adapter.delete_entity("e1") is True


class TestNeptuneRelationshipCRUD:
    """Relationship add/get/delete."""

    def test_add_relationship(self, adapter) -> None:
        """add_relationship() sends CREATE and returns rel with id."""
        _mock_query(adapter, {"results": [{"r": {}}]})
        rel = Relationship(
            id="r1", type="KNOWS", source_id="e1", target_id="e2",
        )
        result = adapter.add_relationship(rel)
        assert result.id == "r1"
        assert result.type == "KNOWS"

    def test_get_relationship_found(self, adapter) -> None:
        """get_relationship() returns Relationship when found."""
        _mock_query(adapter, {
            "results": [{"r": {"id": "r1", "since": 2020}}],
        })
        result = adapter.get_relationship("r1")
        assert result is not None
        assert result.id == "r1"

    def test_get_relationship_not_found(self, adapter) -> None:
        """get_relationship() returns None when not found."""
        _mock_query(adapter, {"results": []})
        assert adapter.get_relationship("missing") is None

    def test_delete_relationship(self, adapter) -> None:
        """delete_relationship() returns True."""
        _mock_query(adapter, {"results": []})
        assert adapter.delete_relationship("r1") is True
