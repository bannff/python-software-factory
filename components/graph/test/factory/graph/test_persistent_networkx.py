"""Tests for PersistentNetworkXGraph adapter.

Verifies:
- Save/load round-trip preserves nodes, edges, attributes
- Empty-graph boot (no prior snapshot)
- Atomic write safety (partial write doesn't corrupt)
- Backend selection in GraphRuntime
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from factory.graph.runtime.adapters.persistent_networkx import (
    PersistentNetworkXGraph,
    _SNAPSHOT_KEY,
)
from factory.graph.runtime.adapters.persistent_networkx_snapshot import SnapshotIntegrityError
from factory.graph.runtime.ports import Entity, Relationship
from factory.storage.runtime.adapters.blob_local import LocalBlobStore


@pytest.fixture
def blob_store(tmp_path: Path) -> LocalBlobStore:
    """Create a real LocalBlobStore in a temp dir."""
    return LocalBlobStore(root_path=str(tmp_path / "blobs"))


@pytest.fixture
def graph(blob_store: LocalBlobStore) -> PersistentNetworkXGraph:
    """Create a PersistentNetworkXGraph backed by the temp blob store."""
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=blob_store,
    ):
        return PersistentNetworkXGraph()


@pytest.fixture
def make_graph(blob_store: LocalBlobStore):
    """Factory to create fresh PersistentNetworkXGraph instances sharing the same store."""
    def _make(**kwargs):
        with patch(
            "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
            return_value=blob_store,
        ):
            return PersistentNetworkXGraph(**kwargs)
    return _make


class TestRoundTrip:
    """Save -> load round-trip preserves graph state."""

    def test_entities_survive_restart(self, blob_store, make_graph):
        """Entities added to one instance are queryable from a fresh instance."""
        g1 = make_graph()
        g1.add_entity(Entity(id="alice", type="Person", properties={"age": 30}, labels=["human"]))
        g1.add_entity(Entity(id="bob", type="Person", properties={"age": 25}, labels=["human"]))

        # Simulate restart: create a fresh instance reading from same store
        g2 = make_graph()
        alice = g2.get_entity("alice")
        assert alice is not None
        assert alice.type == "Person"
        assert alice.properties["age"] == 30
        assert "human" in alice.labels

        bob = g2.get_entity("bob")
        assert bob is not None
        assert bob.properties["age"] == 25

    def test_user_id_property_survives_snapshot_reload(self, make_graph):
        """Snapshot identity metadata must not overwrite a user ``id`` property."""
        graph = make_graph()
        graph.add_entity(Entity(
            id="varietal-1", type="Varietal",
            properties={"id": "v-1", "name": "Pinot Noir"},
        ))
        graph.add_entity(Entity(id="finding-1", type="Finding", properties={"run_id": "r1"}))
        graph.add_relationship(Relationship(
            id="rel-1", type="TASTED_AS", source_id="finding-1", target_id="varietal-1",
        ))

        reloaded = make_graph()
        varietal = reloaded.get_entity("varietal-1")
        assert varietal is not None
        assert varietal.properties["id"] == "v-1"
        assert varietal.properties["name"] == "Pinot Noir"

    def test_sentinel_like_properties_survive_snapshot_reload(self, make_graph):
        """Node identity never shares a namespace with user attributes."""
        graph = make_graph()
        properties = {
            "id": "user-visible-id",
            "__factory_node_id__": "user-sentinel",
            "__factory_snapshot_internal__": "user-internal",
        }
        graph.add_entity(Entity(
            id="source", type="Node", properties=properties, labels=[],
        ))
        graph.add_entity(Entity(id="target", type="Node", properties={}, labels=[]))
        graph.add_relationship(Relationship(
            id="edge", type="RELATED", source_id="source", target_id="target",
        ))

        reloaded = make_graph()
        restored = reloaded.get_entity("source")
        assert restored is not None
        assert restored.properties == properties
        assert reloaded.get_relationship("edge") is not None

    def test_relationships_survive_restart(self, blob_store, make_graph):
        """Edges are persisted and queryable after reload."""
        g1 = make_graph()
        g1.add_entity(Entity(id="a", type="Node", properties={}, labels=[]))
        g1.add_entity(Entity(id="b", type="Node", properties={}, labels=[]))
        g1.add_relationship(Relationship(
            id="r1", type="KNOWS", source_id="a", target_id="b",
            properties={"since": 2020},
        ))

        g2 = make_graph()
        rel = g2.get_relationship("r1")
        assert rel is not None
        assert rel.type == "KNOWS"
        assert rel.source_id == "a"
        assert rel.target_id == "b"
        assert rel.properties["since"] == 2020

    def test_delete_entity_persists(self, blob_store, make_graph):
        """Deletions are persisted — deleted nodes don't reappear."""
        g1 = make_graph()
        g1.add_entity(Entity(id="x", type="Temp", properties={}, labels=[]))
        assert g1.get_entity("x") is not None
        g1.delete_entity("x")

        g2 = make_graph()
        assert g2.get_entity("x") is None

    def test_update_entity_persists(self, blob_store, make_graph):
        """Updated attributes are preserved through restart."""
        g1 = make_graph()
        g1.add_entity(Entity(id="e1", type="Thing", properties={"v": 1}, labels=[]))
        g1.update_entity(Entity(id="e1", type="Thing", properties={"v": 99}, labels=["updated"]))

        g2 = make_graph()
        e = g2.get_entity("e1")
        assert e is not None
        assert e.properties["v"] == 99
        assert "updated" in e.labels

    def test_set_finding_state_persists(self, blob_store, make_graph):
        """set_finding_state mutations survive restart."""
        g1 = make_graph()
        g1.add_entity(Entity(id="f1", type="Finding", properties={"state": "candidate"}, labels=[]))
        g1.set_finding_state("f1", "verified")

        g2 = make_graph()
        e = g2.get_entity("f1")
        assert e is not None
        assert e.properties["state"] == "verified"


class TestEmptyBoot:
    """Empty-graph boot (no prior snapshot)."""

    def test_fresh_start_no_snapshot(self, blob_store):
        """Graph initializes cleanly when no snapshot exists."""
        with patch(
            "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
            return_value=blob_store,
        ):
            g = PersistentNetworkXGraph()
        health = g.health_check()
        assert health.healthy is True
        assert health.node_count == 0
        assert health.edge_count == 0
        assert health.backend == "persistent_networkx"

    def test_corrupt_snapshot_is_rejected_without_overwrite(self, blob_store):
        """Invalid committed state fails closed and remains available for recovery."""
        corrupt_snapshot = b"not valid json!!!"
        blob_store.put(_SNAPSHOT_KEY, corrupt_snapshot)
        with patch(
            "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
            return_value=blob_store,
        ):
            with pytest.raises(SnapshotIntegrityError, match="valid UTF-8 JSON"):
                PersistentNetworkXGraph()
        stored, _ = blob_store.get(_SNAPSHOT_KEY)
        assert stored == corrupt_snapshot


class TestAtomicWrite:
    """Atomic/partial-write safety."""

    def test_failed_persist_does_not_corrupt_existing(self, blob_store, make_graph):
        """If persistence fails mid-write, the prior snapshot remains intact."""
        g1 = make_graph()
        g1.add_entity(Entity(
            id="safe", type="Node", properties={"__factory_node_id__": "survives"}, labels=[],
        ))

        # Verify snapshot exists
        assert blob_store.exists(_SNAPSHOT_KEY)

        # Now make the store fail on the NEXT put
        original_put = blob_store.put

        def failing_put(*args, **kwargs):
            raise IOError("Disk full!")

        blob_store.put = failing_put

        # A failed write rejects and rolls back the mutation.
        from factory.graph.runtime.adapters.persistent_networkx import GraphPersistenceError
        with pytest.raises(GraphPersistenceError):
            g1.add_entity(Entity(id="unsafe", type="Node", properties={}, labels=[]))

        # Restore the store and verify the last durable snapshot remains authoritative.
        blob_store.put = original_put
        g2 = make_graph()
        assert g1.get_entity("unsafe") is None
        assert g2.get_entity("safe") is not None
        assert g2.get_entity("safe").properties["__factory_node_id__"] == "survives"
        assert g2.get_entity("unsafe") is None


class TestRuntimeIntegration:
    """GraphRuntime selects persistent_networkx correctly."""

    def test_runtime_creates_persistent_backend(self, blob_store):
        """GraphRuntime('persistent_networkx') creates PersistentNetworkXGraph."""
        from factory.graph.runtime.runtime import GraphRuntime

        with patch(
            "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
            return_value=blob_store,
        ):
            runtime = GraphRuntime(config={"default_backend": "persistent_networkx"})
            graph = runtime.get_graph("persistent_networkx")
        assert isinstance(graph, PersistentNetworkXGraph)

    def test_persistent_is_in_available_backends(self):
        """persistent_networkx appears in available_backends list."""
        from factory.graph.runtime.runtime import GraphRuntime
        assert "persistent_networkx" in GraphRuntime.available_backends()


class TestLargeGraph:
    """Verify serialization handles non-trivial graph sizes."""

    def test_100_nodes_round_trip(self, blob_store, make_graph):
        """100 nodes + edges round-trip correctly."""
        g1 = make_graph()
        for i in range(100):
            g1.add_entity(Entity(id=f"n{i}", type="Node", properties={"idx": i}, labels=[]))
        for i in range(99):
            g1.add_relationship(Relationship(
                id=f"e{i}", type="NEXT", source_id=f"n{i}", target_id=f"n{i+1}",
                properties={},
            ))

        g2 = make_graph()
        health = g2.health_check()
        assert health.node_count == 100
        assert health.edge_count == 99

        # Spot-check
        n50 = g2.get_entity("n50")
        assert n50 is not None
        assert n50.properties["idx"] == 50
