"""Monotonic reconciliation over the same Graph projection semantics."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .neighborhood import encode_node_id
from .ports import Entity
from .relationship_projection import ProjectionRecord, apply_projection


class ReconcileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ReconcileRecord(ReconcileModel):
    subject_id: str
    revision: int
    payload_digest: str
    record: ProjectionRecord


class ReconcileResult(ReconcileModel):
    scanned: int
    applied: int
    duplicates: int
    tombstones: int
    last_ordinal: int
    next_cursor: str | None


def reconcile_projection(
    graph, *, tenant_id: str, owner_id: str, source_system: str,
    snapshot_id: str, snapshot_digest: str, ordinal_start: int,
    cursor: str | None, next_cursor: str | None, page_digest: str,
    records: tuple[ReconcileRecord | dict, ...],
) -> ReconcileResult:
    cursor_id = encode_node_id(
        "projection-cursor", tenant_id, owner_id, source_system,
    )
    existing = graph.get_entity(cursor_id)
    state = {} if existing is None else existing.properties
    if existing is not None and _is_replay(
        state, ordinal_start, page_digest, next_cursor,
    ):
        return ReconcileResult(
            scanned=len(records), applied=0, duplicates=len(records),
            tombstones=0, last_ordinal=int(state["last_ordinal"]),
            next_cursor=next_cursor,
        )
    _validate_progress(
        state, snapshot_id, snapshot_digest, ordinal_start, cursor,
    )
    applied = duplicates = tombstones = 0
    for raw in records:
        item = ReconcileRecord.model_validate(raw)
        result = apply_projection(
            graph, tenant_id=tenant_id, owner_id=owner_id,
            subject_id=item.subject_id, revision=item.revision,
            payload_digest=item.payload_digest, record=item.record,
        )
        if result.status in {"created", "updated"}:
            applied += 1
        elif result.status in {"matched", "stale"}:
            duplicates += 1
        elif result.status == "tombstoned":
            tombstones += 1
        else:
            raise ValueError("projection reconciliation conflict")
    last = ordinal_start + len(records) - 1
    cursor_entity = Entity(cursor_id, "ProjectionCursor", {
        "tenant_id": tenant_id, "principal_id": owner_id,
        "source_system": source_system, "snapshot_id": snapshot_id,
        "snapshot_digest": snapshot_digest, "last_ordinal": last,
        "next_cursor": next_cursor, "last_page_start": ordinal_start,
        "last_page_digest": page_digest,
    })
    graph.add_entity(cursor_entity) if existing is None \
        else graph.update_entity(cursor_entity)
    return ReconcileResult(
        scanned=len(records), applied=applied, duplicates=duplicates,
        tombstones=tombstones, last_ordinal=last, next_cursor=next_cursor,
    )


def _validate_progress(
    state: dict, snapshot_id: str, snapshot_digest: str,
    ordinal_start: int, cursor: str | None,
) -> None:
    if not state:
        if ordinal_start != 0 or cursor is not None:
            raise ValueError("initial reconciliation must start at zero")
        return
    if state.get("snapshot_id") != snapshot_id \
            or state.get("snapshot_digest") != snapshot_digest:
        raise ValueError("reconciliation snapshot mismatch")
    if cursor != state.get("next_cursor") \
            or ordinal_start != int(state.get("last_ordinal", -1)) + 1:
        raise ValueError("reconciliation cursor is not monotonic")


def _is_replay(
    state: dict, ordinal_start: int, page_digest: str,
    next_cursor: str | None,
) -> bool:
    return bool(state) and (
        state.get("last_page_start") == ordinal_start
        and state.get("last_page_digest") == page_digest
        and state.get("next_cursor") == next_cursor
    )


__all__ = ["ReconcileRecord", "ReconcileResult", "reconcile_projection"]
