"""Owner-scoped SQLite operations for Workflow loop policy state."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from ..loop_models import CycleState, LoopCycleRecord, LoopRecord, LoopState

logger = logging.getLogger(__name__)


def _parse_loop_row(raw_json: str, loop_id: str) -> LoopRecord | None:
    """Item 12(b)/(c) (owner smoke #2): the read path must never crash the
    whole caller because ONE row predates a stricter invariant (e.g. the
    ``next_cycle``/``last_settled_cycle`` contiguity check, or the
    tz-aware timestamp validator). Skip that row and log its real
    validation message — never silently drop the REST of the response,
    and never fabricate a value for the bad row. The write path stays
    exactly as strict as it is today; this is read-side tolerance only.
    """
    try:
        return LoopRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        logger.error(
            "workflow_loop_row_unreadable loop_id=%s error=%s", loop_id, exc,
        )
        return None


def create_loop(connect: Any, record: LoopRecord) -> LoopRecord:
    raw = record.model_dump_json()
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO workflow_loops VALUES(?,?,?,?,?,?,?)",
                (record.tenant_id, record.owner_id, record.loop_id,
                 record.state.value, record.revision,
                 record.updated_at.isoformat(), raw),
            )
        except sqlite3.IntegrityError:
            existing = get_loop(connect, record.tenant_id, record.owner_id, record.loop_id)
            if existing == record:
                return existing
            raise ValueError("loop identity conflict")
    return record


def get_loop(connect: Any, tenant: str, owner: str, loop_id: str) -> LoopRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT raw_json FROM workflow_loops WHERE tenant_id=? AND owner_id=? AND loop_id=?",
            (tenant, owner, loop_id),
        ).fetchone()
    return _parse_loop_row(row["raw_json"], loop_id) if row else None


def list_loops(connect: Any, tenant: str, owner: str, limit: int) -> list[LoopRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT loop_id, raw_json FROM workflow_loops WHERE tenant_id=? AND owner_id=? "
            "ORDER BY updated_at DESC,loop_id LIMIT ?",
            (tenant, owner, max(1, min(limit, 1000))),
        ).fetchall()
    parsed = (_parse_loop_row(row["raw_json"], row["loop_id"]) for row in rows)
    return [loop for loop in parsed if loop is not None]


def set_loop_state(
    connect: Any, record: LoopRecord, state: LoopState,
    reason: str | None, expected_revision: int,
) -> LoopRecord | None:
    now = datetime.now(timezone.utc)
    updated = record.model_copy(update={
        "state": state, "terminal_reason": reason,
        "revision": expected_revision + 1, "updated_at": now,
    })
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE workflow_loops SET state=?,revision=?,updated_at=?,raw_json=? "
            "WHERE tenant_id=? AND owner_id=? AND loop_id=? AND revision=?",
            (state.value, updated.revision, now.isoformat(), updated.model_dump_json(),
             record.tenant_id, record.owner_id, record.loop_id, expected_revision),
        )
    return updated if cursor.rowcount == 1 else None


def mark_blocker_projected(
    connect: Any, record: LoopRecord, expected_revision: int,
) -> LoopRecord | None:
    now = datetime.now(timezone.utc)
    updated = record.model_copy(update={
        "blocker_projected": True, "revision": expected_revision + 1,
        "updated_at": now,
    })
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE workflow_loops SET revision=?,updated_at=?,raw_json=? "
            "WHERE tenant_id=? AND owner_id=? AND loop_id=? AND revision=? "
            "AND state='blocked' AND raw_json LIKE '%\"blocker_projected\":false%'",
            (updated.revision, now.isoformat(), updated.model_dump_json(),
             record.tenant_id, record.owner_id, record.loop_id, expected_revision),
        )
    return updated if cursor.rowcount == 1 else None


def create_cycle(connect: Any, record: LoopCycleRecord) -> LoopCycleRecord:
    raw = record.model_dump_json()
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO workflow_loop_cycles VALUES(?,?,?,?,?,?,?,?,?,?)",
                (record.tenant_id, record.owner_id, record.loop_id, record.cycle,
                 record.schedule_id, record.workflow_run_id, record.state.value,
                 record.revision, record.updated_at.isoformat(), raw),
            )
        except sqlite3.IntegrityError:
            existing = get_cycle(
                connect, record.tenant_id, record.owner_id, record.loop_id, record.cycle,
            )
            if existing == record:
                return existing
            raise ValueError("loop cycle identity conflict")
    return record


def get_cycle(
    connect: Any, tenant: str, owner: str, loop_id: str, cycle: int,
) -> LoopCycleRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT raw_json FROM workflow_loop_cycles WHERE tenant_id=? "
            "AND owner_id=? AND loop_id=? AND cycle=?",
            (tenant, owner, loop_id, cycle),
        ).fetchone()
    return LoopCycleRecord.model_validate_json(row["raw_json"]) if row else None


def list_cycles(connect: Any, state: CycleState, limit: int) -> list[LoopCycleRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT raw_json FROM workflow_loop_cycles WHERE state=? "
            "ORDER BY updated_at,loop_id,cycle LIMIT ?",
            (state.value, max(1, min(limit, 1000))),
        ).fetchall()
    return [LoopCycleRecord.model_validate_json(row["raw_json"]) for row in rows]


def set_cycle_state(
    connect: Any, record: LoopCycleRecord, state: CycleState,
    workflow_run_id: str | None, expected_revision: int,
) -> LoopCycleRecord | None:
    now = datetime.now(timezone.utc)
    updated = record.model_copy(update={
        "state": state, "workflow_run_id": workflow_run_id,
        "revision": expected_revision + 1, "updated_at": now,
    })
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE workflow_loop_cycles SET state=?,workflow_run_id=?,revision=?,"
            "updated_at=?,raw_json=? WHERE tenant_id=? AND owner_id=? AND loop_id=? "
            "AND cycle=? AND revision=?",
            (state.value, workflow_run_id, updated.revision, now.isoformat(),
             updated.model_dump_json(), record.tenant_id, record.owner_id,
             record.loop_id, record.cycle, expected_revision),
        )
    return updated if cursor.rowcount == 1 else None


def list_unprojected_blockers(connect: Any, limit: int) -> list[LoopRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT loop_id, raw_json FROM workflow_loops WHERE state='blocked' "
            "AND raw_json LIKE '%\"blocker_projected\":false%' "
            "ORDER BY updated_at,loop_id LIMIT ?",
            (max(1, min(limit, 1000)),),
        ).fetchall()
    parsed = (_parse_loop_row(row["raw_json"], row["loop_id"]) for row in rows)
    return [loop for loop in parsed if loop is not None]


__all__ = ["create_cycle", "create_loop", "get_cycle", "get_loop", "list_cycles",
           "list_loops", "list_unprojected_blockers", "mark_blocker_projected",
           "set_cycle_state", "set_loop_state"]
