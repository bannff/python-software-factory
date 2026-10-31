"""Tests for NetworkX graph adapter."""

import pytest

from factory.graph.runtime.runtime import GraphRuntime, reset_runtime
from factory.graph.runtime.ports import Entity, Relationship


class TestNetworkXGraph:
    """Tests for NetworkX graph adapter."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_add_and_get_entity(self) -> None:
        """Should add and retrieve entity."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        entity = Entity(id="e1", type="Person", properties={"name": "Alice"})
        graph.add_entity(entity)

        result = graph.get_entity("e1")
        assert result is not None
        assert result.id == "e1"
        assert result.type == "Person"
        assert result.properties["name"] == "Alice"

    def test_get_nonexistent_entity(self) -> None:
        """Should return None for nonexistent entity."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")
        result = graph.get_entity("nonexistent")
        assert result is None

    def test_update_entity(self) -> None:
        """Should update entity properties."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        entity = Entity(id="e1", type="Person", properties={"name": "Alice"})
        graph.add_entity(entity)

        updated = Entity(
            id="e1", type="Person", properties={"name": "Alice", "age": 30}
        )
        graph.update_entity(updated)

        result = graph.get_entity("e1")
        assert result.properties["age"] == 30

    def test_delete_entity(self) -> None:
        """Should delete entity."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        entity = Entity(id="e1", type="Person")
        graph.add_entity(entity)
        assert graph.get_entity("e1") is not None

        deleted = graph.delete_entity("e1")
        assert deleted is True
        assert graph.get_entity("e1") is None

    def test_add_and_get_relationship(self) -> None:
        """Should add and retrieve relationship."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))

        rel = Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        graph.add_relationship(rel)

        result = graph.get_relationship("r1")
        assert result is not None
        assert result.id == "r1"
        assert result.type == "KNOWS"

    def test_delete_relationship(self) -> None:
        """Should delete relationship."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))
        graph.add_relationship(
            Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        )

        deleted = graph.delete_relationship("r1")
        assert deleted is True
        assert graph.get_relationship("r1") is None

    def test_get_neighbors(self) -> None:
        """Should get neighboring entities."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))
        graph.add_entity(Entity(id="e3", type="Person"))
        graph.add_entity(Entity(id="e4", type="Person"))
        graph.add_relationship(
            Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        )
        graph.add_relationship(
            Relationship(id="r2", type="KNOWS", source_id="e1", target_id="e3")
        )
        graph.add_relationship(
            Relationship(id="r3", type="KNOWS", source_id="e1", target_id="e4")
        )

        neighbors = graph.get_neighbors("e1", direction="out", limit=2)
        assert [n.id for n in neighbors] == ["e2", "e3"]

    @pytest.mark.parametrize("limit", [0, 201])
    def test_get_neighbors_rejects_invalid_limit(self, limit: int) -> None:
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        with pytest.raises(ValueError, match="neighbor limit"):
            graph.get_neighbors("e1", limit=limit)

    def test_find_path(self) -> None:
        """Should find path between entities."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))
        graph.add_entity(Entity(id="e3", type="Person"))
        graph.add_relationship(
            Relationship(id="r1", type="KNOWS", source_id="e1", target_id="e2")
        )
        graph.add_relationship(
            Relationship(id="r2", type="KNOWS", source_id="e2", target_id="e3")
        )

        path = graph.find_path("e1", "e3")
        assert path is not None
        assert path.length == 2
        assert len(path.entities) == 3

    def test_find_path_no_path(self) -> None:
        """Should return None when no path exists."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))
        # No relationship between them

        path = graph.find_path("e1", "e2")
        assert path is None

    def test_find_entities_by_type(self) -> None:
        """Should find entities by type."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.add_entity(Entity(id="e2", type="Person"))
        graph.add_entity(Entity(id="e3", type="Company"))

        people = graph.find_entities(entity_type="Person")
        assert len(people) == 2

    def test_find_entities_by_properties(self) -> None:
        """Should find entities by properties."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person", properties={"city": "NYC"}))
        graph.add_entity(Entity(id="e2", type="Person", properties={"city": "LA"}))
        graph.add_entity(Entity(id="e3", type="Person", properties={"city": "NYC"}))

        nyc_people = graph.find_entities(properties={"city": "NYC"})
        assert len(nyc_people) == 2

    def test_add_entity_with_reserved_type_property(self) -> None:
        """Caller property 'type' must not crash and must be preserved."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(
            Entity(id="e1", type="Person", properties={"type": "caller-type"})
        )

        result = graph.get_entity("e1")
        assert result is not None
        assert result.type == "Person"  # canonical wins
        assert result.properties["prop_type"] == "caller-type"  # preserved
        assert "type" not in result.properties

    def test_add_entity_with_reserved_labels_property(self) -> None:
        """Caller property 'labels' must not crash and must be preserved."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(
            Entity(
                id="e1", type="Person", labels=["A", "B"],
                properties={"labels": "caller-labels"},
            )
        )

        result = graph.get_entity("e1")
        assert result is not None
        assert result.labels == ["A", "B"]  # canonical wins
        assert result.properties["prop_labels"] == "caller-labels"
        assert "labels" not in result.properties

    def test_add_entity_with_both_reserved_properties(self) -> None:
        """Both reserved keys collide simultaneously without crashing."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(
            Entity(
                id="e1", type="Person", labels=["L1"],
                properties={"type": "ct", "labels": "cl", "keep": 1},
            )
        )

        result = graph.get_entity("e1")
        assert result is not None
        assert result.type == "Person"
        assert result.labels == ["L1"]
        assert result.properties["prop_type"] == "ct"
        assert result.properties["prop_labels"] == "cl"
        assert result.properties["keep"] == 1

    def test_update_entity_with_reserved_properties(self) -> None:
        """update_entity handles reserved-key collisions identically."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")

        graph.add_entity(Entity(id="e1", type="Person"))
        graph.update_entity(
            Entity(
                id="e1", type="Person", labels=["X"],
                properties={"type": "ut", "labels": "ul", "age": 30},
            )
        )

        result = graph.get_entity("e1")
        assert result is not None
        assert result.type == "Person"
        assert result.labels == ["X"]
        assert result.properties["prop_type"] == "ut"
        assert result.properties["prop_labels"] == "ul"
        assert result.properties["age"] == 30

    def test_health_check(self) -> None:
        """Should return healthy status."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")
        graph.add_entity(Entity(id="e1", type="Person"))

        health = graph.health_check()
        assert health.healthy is True
        assert health.backend == "networkx"
        assert health.node_count == 1
