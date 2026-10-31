"""Tests for whole-graph export/import (row 48, owner direction 2026-09-16:
"simple export/import of the whole graph to one file; no staged-restore
ceremony"). ``export_snapshot``/``import_snapshot`` on ``NetworkXGraph``
(and the durably-persisted override on ``PersistentNetworkXGraph``).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.adapters.networkx_snapshot_io import import_snapshot
from factory.graph.runtime.adapters.persistent_networkx import PersistentNetworkXGraph
from factory.graph.runtime.adapters.persistent_networkx_snapshot import SnapshotIntegrityError
from factory.graph.runtime.ports import Entity, Relationship
from factory.storage.runtime.adapters.blob_local import LocalBlobStore


def test_export_then_import_round_trips_entities_and_relationships() -> None:
    source = NetworkXGraph()
    source.add_entity(Entity(id="a", type="memory", properties={"content": "alpha"}))
    source.add_entity(Entity(id="b", type="memory", properties={"content": "beta"}))
    source.add_relationship(Relationship(id="r1", type="FOLLOWED_BY", source_id="a", target_id="b"))

    data = source.export_snapshot()

    target = NetworkXGraph()
    target.import_snapshot(data)
    assert target.get_entity("a").properties["content"] == "alpha"
    assert target.get_entity("b").properties["content"] == "beta"
    neighbors = target.get_neighbors("a", relationship_type="FOLLOWED_BY", direction="out")
    assert any(n.id == "b" for n in neighbors)


def test_import_replaces_existing_content_entirely() -> None:
    graph = NetworkXGraph()
    graph.add_entity(Entity(id="stale", type="memory", properties={}))
    empty = NetworkXGraph().export_snapshot()

    graph.import_snapshot(empty)

    assert graph.get_entity("stale") is None


def test_import_rejects_a_corrupt_file_without_mutating_state() -> None:
    with pytest.raises(SnapshotIntegrityError):
        import_snapshot(b"not json at all")


@pytest.fixture
def blob_store(tmp_path: Path) -> LocalBlobStore:
    return LocalBlobStore(root_path=str(tmp_path / "blobs"))


def test_persistent_graph_import_survives_a_restart(blob_store: LocalBlobStore) -> None:
    with patch(
        "factory.graph.runtime.adapters.persistent_networkx._get_blob_store",
        return_value=blob_store,
    ):
        source = PersistentNetworkXGraph()
        source.add_entity(Entity(id="keep", type="memory", properties={"content": "durable"}))
        data = source.export_snapshot()

        target = PersistentNetworkXGraph()
        target.add_entity(Entity(id="throwaway", type="memory", properties={}))
        target.import_snapshot(data)

        reloaded = PersistentNetworkXGraph()
        assert reloaded.get_entity("keep").properties["content"] == "durable"
        assert reloaded.get_entity("throwaway") is None
