"""Atomic Graph provenance projection operations for NetworkX adapters."""
from __future__ import annotations

from typing import Any

from ..provenance_models import (
    DurableSourcePage, GraphRelationshipWrite, GraphRebuildCheckpoint,
    GraphRebuildRequest, GraphRebuildResult, GraphTombstone, GraphWriteResult,
    checkpoint_digest, immutable_digest, relationship_id, source_key,
    source_page_digest, tombstone_key,
)
from .networkx_edges import remove_edge_id


def _state(adapter: Any) -> dict[str, Any]:
    graph = adapter._get_graph()
    state = graph.graph.setdefault("provenance", {})
    state.setdefault("relationships", {})
    state.setdefault("tombstones", {})
    state.setdefault("checkpoints", {})
    return state


def _edge(adapter: Any, write: GraphRelationshipWrite) -> None:
    graph = adapter._get_graph()
    rid = relationship_id(write)
    remove_edge_id(graph, rid)
    graph.add_edge(
        write.source_endpoint, write.target_endpoint, key=rid,
        id=rid, type=write.relation_type,
        source_system=write.source_system, source_identity=write.source_identity,
        source_digest=write.source_digest, source_ref=write.source_ref,
        visibility=write.visibility, browse_metadata=write.browse_metadata,
        provenance=True,
    )


def write_relationship(adapter: Any, write: GraphRelationshipWrite) -> GraphWriteResult:
    write = GraphRelationshipWrite.model_validate(write)
    state = _state(adapter)
    rid = relationship_id(write)
    digest = immutable_digest(write)
    if source_key(write.source_system, write.source_identity) in state["tombstones"]:
        return GraphWriteResult(relationship_id=rid, status="tombstoned", immutable_digest=digest)
    existing = state["relationships"].get(rid)
    if existing is not None:
        status = "matched" if existing.get("immutable_digest") == digest else "conflict"
        return GraphWriteResult(
            relationship_id=rid, status=status,
            immutable_digest=digest,
            conflict_ref=None if status == "matched" else str(existing.get("immutable_digest", rid)),
        )
    _edge(adapter, write)
    state["relationships"][rid] = {
        "write": write.model_dump(mode="json"), "immutable_digest": digest,
    }
    return GraphWriteResult(relationship_id=rid, status="created", immutable_digest=digest)


def tombstone_relationship(adapter: Any, tombstone: GraphTombstone) -> GraphWriteResult:
    tombstone = GraphTombstone.model_validate(tombstone)
    state = _state(adapter)
    key = tombstone_key(tombstone)
    old = state["tombstones"].get(key)
    tomb_digest = str(tombstone.source_digest)
    if old is not None and old.get("source_digest") != tomb_digest:
        return GraphWriteResult(
            relationship_id="tombstone-" + key,
            status="conflict", immutable_digest=tomb_digest,
            conflict_ref=str(old.get("source_digest", key)),
        )
    state["tombstones"][key] = tombstone.model_dump(mode="json")
    graph = adapter._get_graph()
    for rid, entry in list(state["relationships"].items()):
        write = entry.get("write", {})
        if source_key(write.get("source_system", ""), write.get("source_identity", "")) != key:
            continue
        remove_edge_id(graph, rid)
        state["relationships"].pop(rid, None)
    return GraphWriteResult(
        relationship_id="tombstone-" + key, status="tombstoned",
        immutable_digest=tomb_digest,
    )


def rebuild(adapter: Any, request: GraphRebuildRequest, page: DurableSourcePage) -> GraphRebuildResult:
    request = GraphRebuildRequest.model_validate(request)
    page = DurableSourcePage.model_validate(page)
    if (request.snapshot_id, request.snapshot_digest) != (page.snapshot_id, page.snapshot_digest):
        raise ValueError("rebuild page does not match immutable snapshot")
    for record in page.records:
        if record.source_system != request.source_system:
            raise ValueError("rebuild record source_system mismatch")

    state = _state(adapter)
    stored = state["checkpoints"].get(request.snapshot_id)
    checkpoint = request.checkpoint
    replay = False
    page_digest = source_page_digest(page)
    page_end = page.ordinal_start + len(page.records) - 1
    if checkpoint is None:
        if request.cursor is not None:
            raise ValueError("initial rebuild cursor requires a checkpoint")
        if page.ordinal_start != 0:
            raise ValueError("initial rebuild must start at ordinal zero")
        if stored is not None:
            raise ValueError("rebuild checkpoint is required for an existing snapshot")
        last = -1
    else:
        if (checkpoint.snapshot_id, checkpoint.snapshot_digest) != (request.snapshot_id, request.snapshot_digest):
            raise ValueError("rebuild checkpoint does not match immutable snapshot")
        if request.cursor != checkpoint.cursor:
            raise ValueError("rebuild cursor does not match checkpoint")
        expected = checkpoint_digest(
            checkpoint.snapshot_id, checkpoint.snapshot_digest,
            checkpoint.last_ordinal, checkpoint.cursor,
            checkpoint.page_ordinal_start, checkpoint.page_digest,
        )
        if checkpoint.checkpoint_digest != expected:
            raise ValueError("rebuild checkpoint digest is invalid")
        if stored is not None and stored.get("checkpoint_digest") != checkpoint.checkpoint_digest:
            raise ValueError("rebuild checkpoint is not the current checkpoint")
        replay = (
            checkpoint.page_ordinal_start is not None
            and checkpoint.page_digest == page_digest
            and checkpoint.page_ordinal_start == page.ordinal_start
            and page.next_cursor == checkpoint.cursor
            and page_end == checkpoint.last_ordinal
        )
        if not replay and page.ordinal_start != checkpoint.last_ordinal + 1:
            raise ValueError("rebuild page has a gap or partial overlap")
        last = checkpoint.last_ordinal

    scanned = applied = duplicates = conflicts = tombstones = 0
    for offset, record in enumerate(page.records):
        ordinal = page.ordinal_start + offset
        scanned += 1
        if replay:
            duplicates += 1
            continue
        if isinstance(record, GraphTombstone):
            result = tombstone_relationship(adapter, record)
        else:
            result = write_relationship(adapter, record)
        if result.status == "created":
            applied += 1
        elif result.status == "matched":
            duplicates += 1
        elif result.status == "conflict":
            conflicts += 1
        elif result.status == "tombstoned":
            tombstones += 1
        last = ordinal
    next_cursor = page.next_cursor
    checkpoint = GraphRebuildCheckpoint(
        snapshot_id=request.snapshot_id, snapshot_digest=request.snapshot_digest,
        last_ordinal=last, cursor=next_cursor,
        page_ordinal_start=page.ordinal_start, page_digest=page_digest,
        checkpoint_digest=checkpoint_digest(
            request.snapshot_id, request.snapshot_digest, last, next_cursor,
            page.ordinal_start, page_digest,
        ),
    )
    state["checkpoints"][request.snapshot_id] = checkpoint.model_dump(mode="json")
    return GraphRebuildResult(
        next_cursor=next_cursor, checkpoint=checkpoint, scanned=scanned,
        applied=applied, duplicates=duplicates, conflicts=conflicts, tombstones=tombstones,
    )


__all__ = ["NetworkXProvenanceMixin", "rebuild", "tombstone_relationship", "write_relationship"]


class NetworkXProvenanceMixin:
    """Expose projection functions as adapter port methods."""

    def write_relationship(self, write: GraphRelationshipWrite) -> GraphWriteResult:
        return write_relationship(self, write)

    def tombstone_relationship(self, tombstone: GraphTombstone) -> GraphWriteResult:
        return tombstone_relationship(self, tombstone)

    def rebuild(
        self, request: GraphRebuildRequest, page: DurableSourcePage,
    ) -> GraphRebuildResult:
        return rebuild(self, request, page)

    def get_run_topology(self, run_id: str, limit: int = 200):
        from .networkx_topology import get_run_topology
        return get_run_topology(self, run_id, limit)
