"""Provenance contract against a live Neo4j (skipped when none is reachable).

Every id carries a per-test prefix and cleanup deletes only that prefix, so a
developer's real graph on the same server is never touched.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.neighborhood import NeighborhoodRequest, encode_node_id
from factory.graph.runtime.provenance_models import (
    DurableSourcePage, GraphRebuildRequest, GraphRelationshipWrite, GraphTombstone,
)


@pytest.fixture
def graph_and_prefix():
    graph = Neo4jGraph(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password"),
    )
    try:
        graph._get_driver().verify_connectivity()
    except Exception:  # noqa: BLE001 - any connect failure means "no server here"
        pytest.skip("no reachable Neo4j")
    prefix = f"t{uuid.uuid4().hex[:10]}:"
    yield graph, prefix
    with graph._get_driver().session(database=graph._database) as session:
        session.run("MATCH (n) WHERE n.id CONTAINS $p DETACH DELETE n", p=prefix)
        session.run("MATCH (n:ProvenanceTombstone) WHERE n.key CONTAINS $p DELETE n", p=prefix)
        session.run("MATCH (n:ProvenanceCheckpoint) WHERE n.snapshot_id STARTS WITH $p DELETE n", p=prefix)


def _write(prefix: str, index: int, digest: str | None = None) -> GraphRelationshipWrite:
    return GraphRelationshipWrite(
        source_system=f"{prefix}source", source_identity=f"item-{index}",
        source_digest=digest or f"digest-{index}", relation_type="relates_to",
        source_endpoint=f"{prefix}s{index}", target_endpoint=f"{prefix}t{index}",
        source_ref=f"ref:{index}", visibility="private", browse_metadata={"ordinal": index},
    )


def _tomb(prefix: str, index: int) -> GraphTombstone:
    return GraphTombstone(
        source_system=f"{prefix}source", source_identity=f"item-{index}",
        source_digest=f"digest-{index}", deleted_at=datetime.now(timezone.utc),
    )


def _edge_count(graph: Neo4jGraph, prefix: str) -> int:
    with graph._get_driver().session(database=graph._database) as session:
        return session.run(
            "MATCH (a)-[r {provenance: true}]->() WHERE a.id CONTAINS $p RETURN count(r) AS c",
            p=prefix,
        ).single()["c"]


def test_write_replay_and_immutable_conflict(graph_and_prefix) -> None:
    graph, prefix = graph_and_prefix
    write = _write(prefix, 1)
    assert graph.write_relationship(write).status == "created"
    assert graph.write_relationship(write).status == "matched"
    changed = write.model_copy(update={"source_digest": "changed"})
    assert graph.write_relationship(changed).status == "conflict"
    assert _edge_count(graph, prefix) == 1


def test_written_edge_is_visible_in_the_neighborhood(graph_and_prefix) -> None:
    graph, prefix = graph_and_prefix
    source = encode_node_id("lesson", "tenant", "owner", f"{prefix}s2")
    target = encode_node_id("kb", "tenant", "owner", f"{prefix}t2")
    graph.write_relationship(_write(prefix, 2).model_copy(update={
        "source_endpoint": source, "target_endpoint": target,
    }))
    result = graph.get_neighborhood(NeighborhoodRequest(
        (source,), "tenant", "owner", max_depth=1,
    ))
    assert {e.id for e in result.entities} >= {source, target}
    assert {r.type for r in result.relationships} == {"relates_to"}


def test_tombstone_removes_the_edge_and_blocks_replay(graph_and_prefix) -> None:
    graph, prefix = graph_and_prefix
    write = _write(prefix, 3)
    graph.write_relationship(write)
    assert graph.tombstone_relationship(_tomb(prefix, 3)).status == "tombstoned"
    assert _edge_count(graph, prefix) == 0
    assert graph.write_relationship(write).status == "tombstoned"


def test_tombstone_with_a_different_digest_conflicts(graph_and_prefix) -> None:
    graph, prefix = graph_and_prefix
    graph.tombstone_relationship(_tomb(prefix, 4))
    other = _tomb(prefix, 4).model_copy(update={"source_digest": "other"})
    assert graph.tombstone_relationship(other).status == "conflict"


def test_rebuild_applies_a_page_then_replays_it_idempotently(graph_and_prefix) -> None:
    graph, prefix = graph_and_prefix
    page = DurableSourcePage(
        snapshot_id=f"{prefix}snap", snapshot_digest="digest-snap", ordinal_start=0,
        records=(_write(prefix, 5), _write(prefix, 6), _tomb(prefix, 6)), next_cursor="next",
    )
    request = GraphRebuildRequest(
        source_system=f"{prefix}source", snapshot_id=page.snapshot_id,
        snapshot_digest=page.snapshot_digest,
    )
    first = graph.rebuild(request, page)
    assert (first.scanned, first.applied, first.tombstones) == (3, 2, 1)
    assert _edge_count(graph, prefix) == 1
    replay = graph.rebuild(request.model_copy(update={
        "cursor": first.next_cursor, "checkpoint": first.checkpoint,
    }), page)
    assert replay.duplicates == 3 and replay.applied == 0
