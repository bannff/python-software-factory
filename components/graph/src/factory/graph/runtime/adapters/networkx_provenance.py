"""Atomic Graph provenance projection operations for NetworkX adapters."""
from __future__ import annotations

from typing import Any

from ..provenance_models import (
    DurableSourcePage, GraphRelationshipWrite, GraphRebuildRequest,
    GraphRebuildResult, GraphTombstone, GraphWriteResult,
    immutable_digest, relationship_id, source_key, tombstone_key,
)
from ..provenance_rebuild import RebuildOps, rebuild as _rebuild
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
    checkpoints = _state(adapter)["checkpoints"]
    return _rebuild(request, page, RebuildOps(
        write=lambda w: write_relationship(adapter, w),
        tombstone=lambda t: tombstone_relationship(adapter, t),
        get_checkpoint=checkpoints.get,
        put_checkpoint=checkpoints.__setitem__,
    ))


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
