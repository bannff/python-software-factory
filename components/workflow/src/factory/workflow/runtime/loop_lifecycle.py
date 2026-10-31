"""Workflow-owned loop policy lifecycle; executes no model or timer."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .loop_models import (
    LoopCycleRecord, LoopRecord, LoopState, TERMINAL_LOOP_STATES,
)
from .loop_stopping import evaluate_stop


class LoopConflictError(RuntimeError):
    pass


class LoopLifecycle:
    def __init__(self, store: Any) -> None:
        self.store = store

    def start(self, record: LoopRecord) -> tuple[LoopRecord, LoopCycleRecord]:
        loop = self.store.create_loop(record)
        cycle = self.store.create_cycle(LoopCycleRecord(
            tenant_id=loop.tenant_id, owner_id=loop.owner_id,
            loop_id=loop.loop_id, cycle=1,
            schedule_id=f"loop_{loop.loop_id}_1",
            scheduled_for=loop.created_at,
            created_at=loop.created_at, updated_at=loop.created_at,
        ))
        return loop, cycle

    def transition(
        self, record: LoopRecord, state: LoopState,
        expected_revision: int, reason: str | None = None,
    ) -> LoopRecord:
        if record.revision != expected_revision or record.state in TERMINAL_LOOP_STATES:
            raise LoopConflictError
        allowed = {
            LoopState.ACTIVE: {LoopState.PAUSED, LoopState.STOPPED},
            LoopState.PAUSED: {LoopState.ACTIVE, LoopState.STOPPED},
        }
        if state not in allowed.get(record.state, set()):
            raise LoopConflictError
        updated = self.store.set_loop_state(record, state, reason, expected_revision)
        if updated is None:
            raise LoopConflictError
        return updated

    def evaluate(
        self, record: LoopRecord, *, now: datetime, sentinel_exists: bool,
    ) -> LoopRecord:
        decision = evaluate_stop(record, now=now, sentinel_exists=sentinel_exists)
        if decision is None:
            return record
        updated = self.store.set_loop_state(
            record, decision.state, decision.reason, record.revision,
        )
        if updated is None:
            raise LoopConflictError
        return updated


__all__ = ["LoopConflictError", "LoopLifecycle"]
