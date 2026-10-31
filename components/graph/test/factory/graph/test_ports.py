"""Tests for graph ports (data classes)."""

from factory.graph.runtime.ports import (
    GraphHealth,
    Entity,
    Relationship,
    GraphPath,
    QueryResult,
)


class TestGraphHealth:
    """Tests for GraphHealth dataclass."""

    def test_healthy_status(self) -> None:
        """Should create healthy status."""
        health = GraphHealth(healthy=True, backend="networkx", node_count=10, edge_count=5)
        assert health.healthy is True
        assert health.backend == "networkx"
        assert health.node_count == 10
        assert health.edge_count == 5

    def test_unhealthy_status(self) -> None:
        """Should create unhealthy status with message."""
        health = GraphHealth(healthy=False, backend="neo4j", message="Connection refused")
        assert health.healthy is False
        assert health.message == "Connection refused"


class TestEntity:
    """Tests for Entity dataclass."""

    def test_basic_entity(self) -> None:
        """Should create basic entity."""
        entity = Entity(id="e1", type="Person")
        assert entity.id == "e1"
        assert entity.type == "Person"
        assert entity.properties == {}
        assert entity.labels == []

    def test_entity_with_properties(self) -> None:
        """Should create entity with properties."""
        entity = Entity(id="e1", type="Person", properties={"name": "Alice", "age": 30})
        assert entity.properties["name"] == "Alice"
        assert entity.properties["age"] == 30

    def test_entity_with_labels(self) -> None:
        """Should create entity with labels."""
        entity = Entity(id="e1", type="Person", labels=["Employee", "Manager"])
        assert "Employee" in entity.labels
        assert "Manager" in entity.labels


class TestRelationship:
    """Tests for Relationship dataclass."""

    def test_basic_relationship(self) -> None:
        """Should create basic relationship."""
        rel = Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        assert rel.id == "r1"
        assert rel.type == "KNOWS"
        assert rel.source_id == "e1"
        assert rel.target_id == "e2"

    def test_relationship_with_properties(self) -> None:
        """Should create relationship with properties."""
        rel = Relationship(
            id="r1",
            type="WORKS_AT",
            source_id="person1",
            target_id="company1",
            properties={"since": 2020, "role": "Engineer"},
        )
        assert rel.properties["since"] == 2020
        assert rel.properties["role"] == "Engineer"


class TestGraphPath:
    """Tests for GraphPath dataclass."""

    def test_empty_path(self) -> None:
        """Should create empty path."""
        path = GraphPath(entities=[], relationships=[])
        assert path.entities == []
        assert path.relationships == []
        assert path.length == 0

    def test_path_with_entities(self) -> None:
        """Should create path with entities."""
        e1 = Entity(id="e1", type="Person")
        e2 = Entity(id="e2", type="Person")
        r1 = Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        path = GraphPath(entities=[e1, e2], relationships=[r1], length=1)
        assert len(path.entities) == 2
        assert len(path.relationships) == 1
        assert path.length == 1


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_empty_result(self) -> None:
        """Should create empty result."""
        result = QueryResult()
        assert result.entities == []
        assert result.relationships == []
        assert result.paths == []

    def test_result_with_entities(self) -> None:
        """Should create result with entities."""
        e1 = Entity(id="e1", type="Person")
        result = QueryResult(entities=[e1])
        assert len(result.entities) == 1
