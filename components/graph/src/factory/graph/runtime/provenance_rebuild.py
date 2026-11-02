"""Backend-neutral replay of one immutable Graph provenance source page.

The page/checkpoint validation is identical for every backend; only how a
record is written and where the checkpoint lives differs, so those are
injected as ``RebuildOps`` (a backend may hold a lock across the whole call,
so ops must not re-enter the adapter's public locking methods).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .provenance_models import (
    DurableSourcePage, GraphRebuildCheckpoint, GraphRebuildRequest,
    GraphRebuildResult, GraphRelationshipWrite, GraphTombstone, GraphWriteResult,
    checkpoint_digest, source_page_digest,
)


@dataclass(frozen=True)
class RebuildOps:
    write: Callable[[GraphRelationshipWrite], GraphWriteResult]
    tombstone: Callable[[GraphTombstone], GraphWriteResult]
    get_checkpoint: Callable[[str], dict[str, Any] | None]
    put_checkpoint: Callable[[str, dict[str, Any]], None]


def rebuild(
    request: GraphRebuildRequest, page: DurableSourcePage, ops: RebuildOps,
) -> GraphRebuildResult:
    request = GraphRebuildRequest.model_validate(request)
    page = DurableSourcePage.model_validate(page)
    if (request.snapshot_id, request.snapshot_digest) != (page.snapshot_id, page.snapshot_digest):
        raise ValueError("rebuild page does not match immutable snapshot")
    for record in page.records:
        if record.source_system != request.source_system:
            raise ValueError("rebuild record source_system mismatch")

    stored = ops.get_checkpoint(request.snapshot_id)
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
            result = ops.tombstone(record)
        else:
            result = ops.write(record)
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
    ops.put_checkpoint(request.snapshot_id, checkpoint.model_dump(mode="json"))
    return GraphRebuildResult(
        next_cursor=next_cursor, checkpoint=checkpoint, scanned=scanned,
        applied=applied, duplicates=duplicates, conflicts=conflicts, tombstones=tombstones,
    )


__all__ = ["RebuildOps", "rebuild"]
