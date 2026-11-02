"""Native Neo4j Graph provenance projection.

Live edges are real relationships carrying the source identity/digest;
tombstones and rebuild checkpoints are bookkeeping nodes. Every write is one
managed transaction, so a replayed or concurrent write cannot half-apply.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..provenance_models import (
    DurableSourcePage, GraphRebuildRequest, GraphRebuildResult,
    GraphRelationshipWrite, GraphTombstone, GraphWriteResult,
    immutable_digest, relationship_id, source_key, tombstone_key,
)
from ..provenance_rebuild import RebuildOps, rebuild as _rebuild

# A relationship type cannot be a Cypher parameter, so it is validated and
# backtick-quoted instead of interpolated raw.
_REL_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def _relationship_type(write: GraphRelationshipWrite) -> str:
    if not _REL_TYPE.fullmatch(write.relation_type):
        raise ValueError("relation_type must be an identifier for the neo4j backend")
    return write.relation_type


def _ensure_node(tx: Any, node_id: str) -> None:
    tx.run(
        "OPTIONAL MATCH (n {id: $id}) WITH n LIMIT 1 WHERE n IS NULL "
        "CREATE (:Node {id: $id})", id=node_id,
    )


def _write_tx(tx: Any, write: GraphRelationshipWrite, rel_type: str) -> GraphWriteResult:
    rid, digest = relationship_id(write), immutable_digest(write)
    key = source_key(write.source_system, write.source_identity)
    if tx.run("MATCH (t:ProvenanceTombstone {key: $k}) RETURN t.key", k=key).single():
        return GraphWriteResult(relationship_id=rid, status="tombstoned", immutable_digest=digest)
    row = tx.run(
        "MATCH ()-[r {id: $rid}]->() RETURN r.immutable_digest AS d LIMIT 1", rid=rid,
    ).single()
    if row is not None:
        matched = row["d"] == digest
        return GraphWriteResult(
            relationship_id=rid, status="matched" if matched else "conflict",
            immutable_digest=digest, conflict_ref=None if matched else str(row["d"]),
        )
    _ensure_node(tx, write.source_endpoint)
    _ensure_node(tx, write.target_endpoint)
    props = {
        "id": rid, "source_system": write.source_system,
        "source_identity": write.source_identity, "source_digest": write.source_digest,
        "source_ref": write.source_ref, "visibility": write.visibility,
        "browse_metadata": json.dumps(write.browse_metadata, sort_keys=True),
        "immutable_digest": digest, "provenance": True,
    }
    tx.run(
        "CALL () { MATCH (n {id: $s}) RETURN n AS a LIMIT 1 } "
        "CALL () { MATCH (n {id: $t}) RETURN n AS b LIMIT 1 } "
        f"CREATE (a)-[r:`{rel_type}`]->(b) SET r = $props",
        s=write.source_endpoint, t=write.target_endpoint, props=props,
    )
    return GraphWriteResult(relationship_id=rid, status="created", immutable_digest=digest)


def _tombstone_tx(tx: Any, tombstone: GraphTombstone) -> GraphWriteResult:
    key, digest = tombstone_key(tombstone), str(tombstone.source_digest)
    old = tx.run(
        "MATCH (t:ProvenanceTombstone {key: $k}) RETURN t.source_digest AS d", k=key,
    ).single()
    if old is not None and old["d"] != digest:
        return GraphWriteResult(
            relationship_id="tombstone-" + key, status="conflict",
            immutable_digest=digest, conflict_ref=str(old["d"]),
        )
    tx.run(
        "MERGE (t:ProvenanceTombstone {key: $k}) SET t.source_digest = $d, t.payload = $p",
        k=key, d=digest, p=tombstone.model_dump_json(),
    )
    tx.run(
        "MATCH ()-[r {provenance: true, source_system: $ss, source_identity: $si}]->() DELETE r",
        ss=tombstone.source_system, si=tombstone.source_identity,
    )
    return GraphWriteResult(
        relationship_id="tombstone-" + key, status="tombstoned", immutable_digest=digest,
    )


class Neo4jProvenanceMixin:
    """Port methods for ``Neo4jGraph`` (needs ``_get_driver`` and ``_database``)."""

    def _write_tx(self, fn: Any) -> Any:
        with self._get_driver().session(database=self._database) as session:
            return session.execute_write(fn)

    def _read_tx(self, fn: Any) -> Any:
        with self._get_driver().session(database=self._database) as session:
            return session.execute_read(fn)

    def write_relationship(self, write: GraphRelationshipWrite) -> GraphWriteResult:
        write = GraphRelationshipWrite.model_validate(write)
        rel_type = _relationship_type(write)
        return self._write_tx(lambda tx: _write_tx(tx, write, rel_type))

    def tombstone_relationship(self, tombstone: GraphTombstone) -> GraphWriteResult:
        tombstone = GraphTombstone.model_validate(tombstone)
        return self._write_tx(lambda tx: _tombstone_tx(tx, tombstone))

    def _get_checkpoint(self, snapshot_id: str) -> dict[str, Any] | None:
        row = self._read_tx(lambda tx: tx.run(
            "MATCH (c:ProvenanceCheckpoint {snapshot_id: $id}) RETURN c.payload AS p",
            id=snapshot_id,
        ).single())
        return None if row is None else json.loads(row["p"])

    def _put_checkpoint(self, snapshot_id: str, payload: dict[str, Any]) -> None:
        self._write_tx(lambda tx: tx.run(
            "MERGE (c:ProvenanceCheckpoint {snapshot_id: $id}) SET c.payload = $p",
            id=snapshot_id, p=json.dumps(payload, sort_keys=True),
        ))

    def rebuild(
        self, request: GraphRebuildRequest, page: DurableSourcePage,
    ) -> GraphRebuildResult:
        return _rebuild(request, page, RebuildOps(
            write=self.write_relationship, tombstone=self.tombstone_relationship,
            get_checkpoint=self._get_checkpoint, put_checkpoint=self._put_checkpoint,
        ))

    def get_run_topology(self, run_id: str, limit: int = 200):
        from .neo4j_topology import get_run_topology
        return get_run_topology(self, run_id, limit)


__all__ = ["Neo4jProvenanceMixin"]
