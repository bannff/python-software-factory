"""Focused durable Graph provenance contract tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from hypothesis import given, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.adapters.persistent_networkx import PersistentNetworkXGraph
from factory.graph.runtime.provenance_models import (
    DurableSourcePage,
    GraphRebuildRequest,
    GraphRelationshipWrite,
    GraphTombstone,
)
from factory.graph.mcp.provenance_models import GraphRebuildInput
from factory.storage.runtime.adapters.blob_local import LocalBlobStore


def _write(index: int, digest: str | None = None) -> GraphRelationshipWrite:
    return GraphRelationshipWrite(
        source_system="source",
        source_identity=f"item-{index}",
        source_digest=digest or f"digest-{index}",
        relation_type="relates_to",
        source_endpoint=f"source:{index}",
        target_endpoint=f"target:{index}",
        source_ref=f"source-ref:{index}",
        visibility="private",
        browse_metadata={"ordinal": index},
    )


def test_write_replay_and_immutable_conflict() -> None:
    graph = NetworkXGraph()
    write = _write(1)

    assert graph.write_relationship(write).status == "created"
    assert graph.write_relationship(write).status == "matched"
    assert graph.write_relationship(write.model_copy(update={"source_digest": "changed"})).status == "conflict"


def test_tombstone_removes_edge_and_blocks_replay() -> None:
    graph = NetworkXGraph()
    write = _write(2)
    graph.write_relationship(write)

    result = graph.tombstone_relationship(GraphTombstone(
        source_system="source", source_identity="item-2",
        source_digest="digest-2", deleted_at=datetime.now(timezone.utc),
    ))

    assert result.status == "tombstoned"
    assert graph.health_check().edge_count == 0
    assert graph.write_relationship(write).status == "tombstoned"


def test_rebuild_checkpoint_replay_and_persistent_restart(tmp_path) -> None:
    store = LocalBlobStore(root_path=str(tmp_path / "blobs"))
    records = (_write(3), _write(4))
    request = GraphRebuildRequest(
        source_system="source", snapshot_id="snapshot-1", snapshot_digest="digest-1",
    )
    page = DurableSourcePage(
        snapshot_id="snapshot-1", snapshot_digest="digest-1", ordinal_start=0,
        records=records, next_cursor="next",
    )
    with patch("factory.graph.runtime.adapters.persistent_networkx._get_blob_store", return_value=store):
        graph = PersistentNetworkXGraph()
        first = graph.rebuild(request, page)
        replay = graph.rebuild(request.model_copy(update={
            "cursor": first.next_cursor, "checkpoint": first.checkpoint,
        }), page)
        restarted = PersistentNetworkXGraph()

    assert (first.scanned, first.applied) == (2, 2)
    assert replay.duplicates == 2
    assert restarted.write_relationship(records[0]).status == "matched"


@given(st.lists(st.integers(min_value=0, max_value=50), unique=True, min_size=1, max_size=8))
def test_replaying_any_ordered_page_converges(indices: list[int]) -> None:
    graph = NetworkXGraph()
    writes = [_write(index) for index in indices]
    first = [graph.write_relationship(write).status for write in writes]
    second = [graph.write_relationship(write).status for write in writes]

    assert first == ["created"] * len(writes)
    assert second == ["matched"] * len(writes)


def test_tombstones_do_not_collide_for_delimiter_containing_keys() -> None:
    graph = NetworkXGraph()
    first = _write(5).model_copy(update={
        "source_system": "a:b", "source_identity": "c",
    })
    second = _write(6).model_copy(update={
        "source_system": "a", "source_identity": "b:c",
    })
    graph.write_relationship(first)
    graph.write_relationship(second)

    tombstoned = graph.tombstone_relationship(GraphTombstone(
        source_system=first.source_system,
        source_identity=first.source_identity,
        source_digest=first.source_digest,
        deleted_at=datetime.now(timezone.utc),
    ))

    assert tombstoned.status == "tombstoned"
    assert graph.write_relationship(first).status == "tombstoned"
    assert graph.write_relationship(second).status == "matched"


def test_rebuild_materializes_source_tombstones_and_checkpoints_them() -> None:
    graph = NetworkXGraph()
    write = _write(7)
    tombstone = GraphTombstone(
        source_system="source", source_identity="item-7",
        source_digest="digest-7", deleted_at=datetime.now(timezone.utc),
    )
    page = DurableSourcePage(
        snapshot_id="snapshot-tombstone", snapshot_digest="digest-tombstone",
        ordinal_start=0, records=(write, tombstone), next_cursor="after-tombstone",
    )
    request = GraphRebuildRequest(
        source_system="source", snapshot_id=page.snapshot_id,
        snapshot_digest=page.snapshot_digest,
    )

    result = graph.rebuild(request, page)

    assert (result.scanned, result.applied, result.tombstones) == (2, 1, 1)
    assert result.checkpoint.last_ordinal == 1
    assert result.checkpoint.cursor == "after-tombstone"
    assert graph.health_check().edge_count == 0
    assert graph.write_relationship(write).status == "tombstoned"

    replay = graph.rebuild(
        request.model_copy(update={
            "cursor": result.next_cursor, "checkpoint": result.checkpoint,
        }),
        page,
    )
    assert replay.duplicates == 2
    assert replay.tombstones == 0
    assert replay.checkpoint.last_ordinal == result.checkpoint.last_ordinal


def test_typed_rebuild_input_accepts_wire_source_tombstones() -> None:
    tombstone = {
        "source_system": "source",
        "source_identity": "item-wire",
        "source_digest": "digest-wire",
        "deleted_at": "2025-01-01T00:00:00Z",
    }
    parsed = GraphRebuildInput(
        source_system="source", snapshot_id="snapshot-wire",
        snapshot_digest="digest-wire", ordinal_start=0, records=[tombstone],
    )

    assert isinstance(parsed.records[0], GraphTombstone)
    assert parsed.records[0].deleted_at.tzinfo is not None
