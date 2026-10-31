"""Atomic SQLite settlement for Workflow loop cycles."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..loop_models import (
    CycleDisposition, CycleState, LoopCycleRecord, LoopRecord,
)
from ..loop_stopping import evaluate_stop


def settle_cycle(
    connect: Any, loop: LoopRecord, cycle: LoopCycleRecord,
    disposition: CycleDisposition, summary: str,
    blocker_digest: str | None, sentinel: bool,
) -> tuple[LoopRecord, LoopCycleRecord, LoopCycleRecord | None] | None:
    now = datetime.now(timezone.utc)
    settled = LoopCycleRecord.model_validate({
        **cycle.model_dump(), "state": CycleState.SETTLED,
        "disposition": disposition, "summary": summary,
        "blocker_digest": blocker_digest, "revision": cycle.revision + 1,
        "updated_at": now,
    })
    progress = LoopRecord.model_validate({
        **loop.model_dump(), "last_settled_cycle": cycle.cycle,
        "next_cycle": cycle.cycle + 1, "blocker_digest": blocker_digest,
        "revision": loop.revision + 1, "updated_at": now,
    })
    decision = evaluate_stop(
        progress, now=now, sentinel_exists=sentinel, disposition=disposition,
    )
    if decision is not None:
        progress = progress.model_copy(update={
            "state": decision.state, "terminal_reason": decision.reason,
        })
    following = None if decision is not None else LoopCycleRecord(
        tenant_id=loop.tenant_id, owner_id=loop.owner_id, loop_id=loop.loop_id,
        cycle=cycle.cycle + 1, schedule_id=f"loop_{loop.loop_id}_{cycle.cycle + 1}",
        scheduled_for=now + timedelta(seconds=loop.interval_seconds),
        created_at=now, updated_at=now,
    )
    with connect() as conn:
        changed_cycle = conn.execute(
            "UPDATE workflow_loop_cycles SET state=?,revision=?,updated_at=?,raw_json=? "
            "WHERE tenant_id=? AND owner_id=? AND loop_id=? AND cycle=? "
            "AND revision=? AND state='running'",
            (settled.state.value, settled.revision, now.isoformat(),
             settled.model_dump_json(), cycle.tenant_id, cycle.owner_id,
             cycle.loop_id, cycle.cycle, cycle.revision),
        ).rowcount
        changed_loop = conn.execute(
            "UPDATE workflow_loops SET state=?,revision=?,updated_at=?,raw_json=? "
            "WHERE tenant_id=? AND owner_id=? AND loop_id=? "
            "AND revision=? AND state='active'",
            (progress.state.value, progress.revision, now.isoformat(),
             progress.model_dump_json(), loop.tenant_id, loop.owner_id,
             loop.loop_id, loop.revision),
        ).rowcount
        if changed_cycle != 1 or changed_loop != 1:
            conn.rollback()
            return None
        if following is not None:
            conn.execute(
                "INSERT INTO workflow_loop_cycles VALUES(?,?,?,?,?,?,?,?,?,?)",
                (following.tenant_id, following.owner_id, following.loop_id,
                 following.cycle, following.schedule_id, None,
                 following.state.value, following.revision,
                 following.updated_at.isoformat(), following.model_dump_json()),
            )
    return progress, settled, following


__all__ = ["settle_cycle"]
