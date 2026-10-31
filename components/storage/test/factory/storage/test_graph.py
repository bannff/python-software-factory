"""Tests for graph storage adapters."""

import pytest

from factory.storage.runtime.adapters.graph_networkx import NetworkXGraphStore


class TestNetworkXGraphStore:
    """Tests for NetworkXGraphStore adapter."""

    @pytest.fixture
    def store(self) -> NetworkXGraphStore:
        """Create a graph store."""
        return NetworkXGraphStore()

    def test_add_and_get_node(self, store: NetworkXGraphStore) -> None:
        """Test adding and retrieving a node."""
        node = store.add_node(["Person"], {"name": "Alice", "age": 30})

        assert node.id is not None
        assert node.labels == ["Person"]
        assert node.properties["name"] == "Alice"

        retrieved = store.get_node(node.id)
        assert retrieved is not None
        assert retrieved.properties["name"] == "Alice"

    def test_add_node_with_id(self, store: NetworkXGraphStore) -> None:
        """Test adding a node with a specific ID."""
        node = store.add_node(["Person"], {"id": "alice-123", "name": "Alice"})
        assert node.id == "alice-123"

        retrieved = store.get_node("alice-123")
        assert retrieved is not None

    def test_update_node(self, store: NetworkXGraphStore) -> None:
        """Test updating node properties."""
        node = store.add_node(["Person"], {"name": "Bob", "age": 25})

        updated = store.update_node(node.id, {"age": 26, "city": "NYC"})
        assert updated is not None
        assert updated.properties["age"] == 26
        assert updated.properties["city"] == "NYC"

    def test_update_nonexistent_node(self, store: NetworkXGraphStore) -> None:
        """Test updating a nonexistent node."""
        result = store.update_node("nonexistent", {"name": "Nobody"})
        assert result is None

    def test_delete_node(self, store: NetworkXGraphStore) -> None:
        """Test deleting a node."""
        node = store.add_node(["Person"], {"name": "Charlie"})
        assert store.get_node(node.id) is not None

        deleted = store.delete_node(node.id)
        assert deleted
        assert store.get_node(node.id) is None

    def test_delete_nonexistent_node(self, store: NetworkXGraphStore) -> None:
        """Test deleting a nonexistent node."""
        deleted = store.delete_node("nonexistent")
        assert not deleted

    def test_add_and_get_edge(self, store: NetworkXGraphStore) -> None:
        """Test adding and retrieving an edge."""
        alice = store.add_node(["Person"], {"id": "alice", "name": "Alice"})
        bob = store.add_node(["Person"], {"id": "bob", "name": "Bob"})

        edge = store.add_edge(alice.id, bob.id, "KNOWS", {"since": 2020})

        assert edge.id is not None
        assert edge.source_id == alice.id
        assert edge.target_id == bob.id
        assert edge.type == "KNOWS"

    def test_get_edges_outgoing(self, store: NetworkXGraphStore) -> None:
        """Test getting outgoing edges."""
        a = store.add_node(["Node"], {"id": "a"})
        b = store.add_node(["Node"], {"id": "b"})
        c = store.add_node(["Node"], {"id": "c"})

        store.add_edge(a.id, b.id, "LINKS")
        store.add_edge(a.id, c.id, "LINKS")

        edges = store.get_edges(a.id, direction="out")
        assert len(edges) == 2

    def test_get_edges_incoming(self, store: NetworkXGraphStore) -> None:
        """Test getting incoming edges."""
        a = store.add_node(["Node"], {"id": "a"})
        b = store.add_node(["Node"], {"id": "b"})

        store.add_edge(a.id, b.id, "LINKS")

        edges = store.get_edges(b.id, direction="in")
        assert len(edges) == 1
        assert edges[0].source_id == a.id

    def test_get_edges_both(self, store: NetworkXGraphStore) -> None:
        """Test getting all edges."""
        a = store.add_node(["Node"], {"id": "a"})
        b = store.add_node(["Node"], {"id": "b"})
        c = store.add_node(["Node"], {"id": "c"})

        store.add_edge(a.id, b.id, "OUT")
        store.add_edge(c.id, b.id, "IN")

        edges = store.get_edges(b.id, direction="both")
        assert len(edges) == 2

    def test_delete_edge(self, store: NetworkXGraphStore) -> None:
        """Test deleting an edge."""
        a = store.add_node(["Node"], {"id": "a"})
        b = store.add_node(["Node"], {"id": "b"})
        edge = store.add_edge(a.id, b.id, "LINKS")

        deleted = store.delete_edge(edge.id)
        assert deleted

        edges = store.get_edges(a.id)
        assert len(edges) == 0

    def test_query(self, store: NetworkXGraphStore) -> None:
        """Test querying the graph."""
        store.add_node(["Person"], {"name": "Alice"})
        store.add_node(["Person"], {"name": "Bob"})

        result = store.query("MATCH (n) RETURN n")
        assert len(result.nodes) == 2

    def test_health_check(self, store: NetworkXGraphStore) -> None:
        """Test health check."""
        health = store.health_check()
        assert health.healthy
        assert health.backend == "networkx"
        assert "nodes" in health.details
        assert "edges" in health.details

    def test_get_nonexistent_node(self, store: NetworkXGraphStore) -> None:
        """Test getting a nonexistent node."""
        result = store.get_node("nonexistent")
        assert result is None
