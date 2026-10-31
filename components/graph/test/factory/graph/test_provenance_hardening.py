"""Hardening tests for multi-edge Graph provenance and rebuild continuity."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch

import networkx as nx
import pytest
from networkx.readwrite import json_graph

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.adapters.persistent_networkx import (
    PersistentNetworkXGraph,
)
from factory.graph.runtime.adapters.persistent_networkx_snapshot import _SNAPSHOT_NODE_ID
from factory.graph.runtime.ports import Entity, Relationship
from factory.graph.runtime.provenance_models import (
    DurableSourcePage,
    GraphRebuildRequest,
    GraphRelationshipWrite,
    GraphTombstone,
)
from factory.storage.runtime.adapters.blob_local import LocalBlobStore


def _write(identity: str, digest: str | None = None) -> GraphRelationshipWrite:
    return GraphRelationshipWrite(
        source_system="telemetry", source_identity=identity,
        source_digest=digest or f"digest-{identity}", relation_type="OBSERVED",
        source_endpoint="telemetry-ref", target_endpoint="entity-target",
        source_ref=f"ref-{identity}", visibility="private",
        browse_metadata={"identity": identity},
    )


def _page(start: int, identities: tuple[str, ...], cursor: str | None) -> DurableSourcePage:
    return DurableSourcePage(
        snapshot_id="snapshot", snapshot_digest="snapshot-digest",
        ordinal_start=start, records=tuple(_write(item) for item in identities),
        next_cursor=cursor,
    )


def _request(cursor: str | None = None, checkpoint=None) -> GraphRebuildRequest:
    return GraphRebuildRequest(
        source_system="telemetry", snapshot_id="snapshot",
        snapshot_digest="snapshot-digest", cursor=cursor, checkpoint=checkpoint,
    )


def test_generic_relationships_share_endpoints_without_overwriting() -> None:
    graph = NetworkXGraph()
    graph.add_entity(Entity(id="source", type="Node"))
    graph.add_entity(Entity(id="target", type="Node"))
    first = Relationship(id="r-1", type="OBSERVED", source_id="source", target_id="target")
    second = Relationship(id="r-2", type="RELATED", source_id="source", target_id="target")

    graph.add_relationship(first)
    graph.add_relationship(second)

    assert graph.health_check().edge_count == 2
    assert graph.get_relationship("r-1") == first
    assert graph.get_relationship("r-2") == second
    assert [item.id for item in graph.get_neighbors("source", direction="out")] == ["target"]
    assert graph.delete_relationship("r-1") is True
    assert graph.get_relationship("r-1") is None
    assert graph.get_relationship("r-2") == second


def test_provenance_tombstone_only_removes_its_source_relationship() -> None:
    graph = NetworkXGraph()
    first = _write("source-1")
    second = _write("source-2")
    graph.write_relationship(first)
    graph.write_relationship(second)

    result = graph.tombstone_relationship(GraphTombstone(
        source_system="telemetry", source_identity="source-1",
        source_digest="digest-source-1", deleted_at=datetime.now(timezone.utc),
    ))

    assert result.status == "tombstoned"
    assert graph.health_check().edge_count == 1
    assert graph.write_relationship(first).status == "tombstoned"
    assert graph.write_relationship(second).status == "matched"


def test_persistent_multiedges_and_legacy_snapshot_migrate(tmp_path) -> None:
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    with patch("factory.graph.runtime.adapters.persistent_networkx._get_blob_store", return_value=store):
        graph = PersistentNetworkXGraph()
        graph.add_relationship(Relationship(id="old-1", type="A", source_id="s", target_id="t"))
        graph.add_relationship(Relationship(id="old-2", type="B", source_id="s", target_id="t"))
        restarted = PersistentNetworkXGraph()
    assert restarted.health_check().edge_count == 2
    assert restarted.get_relationship("old-1") is not None
    assert restarted.get_relationship("old-2") is not None

    legacy = nx.DiGraph()
    legacy.add_edge("legacy-s", "legacy-t", id="legacy-r", type="LEGACY")
    store.put("legacy.json", json.dumps(json_graph.node_link_data(legacy)).encode())
    with patch("factory.graph.runtime.adapters.persistent_networkx._get_blob_store", return_value=store):
        migrated = PersistentNetworkXGraph(snapshot_key="legacy.json")
    assert migrated.get_relationship("legacy-r") is not None
    migrated.add_relationship(Relationship(id="legacy-r-2", type="SECOND", source_id="legacy-s", target_id="legacy-t"))
    assert migrated.health_check().edge_count == 2



@pytest.mark.parametrize("schema_version", [None, 1, 2])
def test_legacy_bare_and_enveloped_node_links_migrate_to_v3(tmp_path, schema_version) -> None:
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    legacy = nx.DiGraph()
    properties = {"marker": f"legacy-{schema_version}"}
    if schema_version == 2:
        properties["id"] = "user-visible-id"
    else:
        properties[_SNAPSHOT_NODE_ID] = "user-sentinel"
    legacy.add_node("legacy-s", **properties)
    legacy.add_edge("legacy-s", "legacy-t", id="legacy-r", type="LEGACY")
    node_link = json_graph.node_link_data(
        legacy, name=_SNAPSHOT_NODE_ID if schema_version == 2 else "id",
    )
    if schema_version is None:
        payload = node_link
    else:
        canonical = json.dumps(node_link, sort_keys=True, separators=(",", ":")).encode()
        payload = {
            "schema_version": schema_version,
            "checksum": hashlib.sha256(canonical).hexdigest(),
            "graph": node_link,
        }
    snapshot_key = f"legacy-{schema_version}.json"
    store.put(snapshot_key, json.dumps(payload).encode())

    with patch("factory.graph.runtime.adapters.persistent_networkx._get_blob_store", return_value=store):
        migrated = PersistentNetworkXGraph(snapshot_key=snapshot_key)
        migrated.add_relationship(Relationship(
            id="legacy-r-2", type="SECOND", source_id="legacy-s", target_id="legacy-t",
        ))

    restored = migrated.get_entity("legacy-s")
    assert restored is not None
    assert restored.properties["marker"] == f"legacy-{schema_version}"
    if schema_version == 2:
        assert restored.properties["id"] == "user-visible-id"
    else:
        assert restored.properties[_SNAPSHOT_NODE_ID] == "user-sentinel"
    assert migrated.health_check().edge_count == 2
    written, _ = store.get(snapshot_key)
    assert json.loads(written)["schema_version"] == 3


def test_rebuild_rejects_bad_initial_and_resumed_continuity() -> None:
    graph = NetworkXGraph()
    with pytest.raises(ValueError, match="ordinal zero"):
        graph.rebuild(_request(), _page(1, ("gap",), "next"))
    with pytest.raises(ValueError, match="requires a checkpoint"):
        graph.rebuild(_request(cursor="unexpected"), _page(0, ("first",), "next"))

    first_page = _page(0, ("first", "second"), "next")
    first = graph.rebuild(_request(), first_page)
    with pytest.raises(ValueError, match="cursor"):
        graph.rebuild(_request(checkpoint=first.checkpoint), _page(2, ("third",), None))
    with pytest.raises(ValueError, match="cursor"):
        graph.rebuild(_request(cursor="wrong", checkpoint=first.checkpoint), _page(2, ("third",), None))
    with pytest.raises(ValueError, match="gap or partial overlap"):
        graph.rebuild(_request(cursor="next", checkpoint=first.checkpoint), _page(3, ("third",), None))
    with pytest.raises(ValueError, match="gap or partial overlap"):
        graph.rebuild(_request(cursor="next", checkpoint=first.checkpoint), _page(1, ("overlap",), None))


def test_rebuild_accepts_only_exact_completed_page_replay() -> None:
    graph = NetworkXGraph()
    page = _page(0, ("first", "second"), "next")
    first = graph.rebuild(_request(), page)

    replay = graph.rebuild(
        _request(cursor="next", checkpoint=first.checkpoint), page,
    )

    assert replay.scanned == 2
    assert replay.duplicates == 2
    assert graph.health_check().edge_count == 2


def test_rebuild_rejects_tampered_checkpoint_digest() -> None:
    graph = NetworkXGraph()
    page = _page(0, ("first",), "next")
    first = graph.rebuild(_request(), page)
    tampered = first.checkpoint.model_copy(update={"page_digest": "tampered"})

    with pytest.raises(ValueError, match="digest"):
        graph.rebuild(_request(cursor="next", checkpoint=tampered), _page(1, ("second",), None))
