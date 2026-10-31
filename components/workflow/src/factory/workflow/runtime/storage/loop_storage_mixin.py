"""Loop policy storage mixin for SQLite Workflow storage."""
from __future__ import annotations

from ..loop_models import (
    CycleDisposition, CycleState, LoopCycleRecord, LoopRecord, LoopState,
)
from . import loop_settlement, loop_storage


class LoopStorageMixin:
    def create_loop(self, record: LoopRecord) -> LoopRecord:
        return loop_storage.create_loop(self._connect, record)

    def get_loop(self, tenant_id: str, owner_id: str, loop_id: str) -> LoopRecord | None:
        return loop_storage.get_loop(self._connect, tenant_id, owner_id, loop_id)

    def list_loops(
        self, tenant_id: str, owner_id: str, limit: int = 100,
    ) -> list[LoopRecord]:
        return loop_storage.list_loops(self._connect, tenant_id, owner_id, limit)

    def set_loop_state(
        self, record: LoopRecord, state: LoopState,
        reason: str | None, expected_revision: int,
    ) -> LoopRecord | None:
        return loop_storage.set_loop_state(
            self._connect, record, state, reason, expected_revision,
        )

    def create_cycle(self, record: LoopCycleRecord) -> LoopCycleRecord:
        return loop_storage.create_cycle(self._connect, record)

    def get_cycle(
        self, tenant_id: str, owner_id: str, loop_id: str, cycle: int,
    ) -> LoopCycleRecord | None:
        return loop_storage.get_cycle(
            self._connect, tenant_id, owner_id, loop_id, cycle,
        )

    def list_cycles(self, state: CycleState, limit: int = 100) -> list[LoopCycleRecord]:
        return loop_storage.list_cycles(self._connect, state, limit)

    def set_cycle_state(
        self, record: LoopCycleRecord, state: CycleState,
        workflow_run_id: str | None, expected_revision: int,
    ) -> LoopCycleRecord | None:
        return loop_storage.set_cycle_state(
            self._connect, record, state, workflow_run_id, expected_revision,
        )


    def settle_cycle(
        self, loop: LoopRecord, cycle: LoopCycleRecord,
        disposition: CycleDisposition, summary: str,
        blocker_digest: str | None, sentinel: bool,
    ):
        return loop_settlement.settle_cycle(
            self._connect, loop, cycle, disposition,
            summary, blocker_digest, sentinel,
        )

    def mark_blocker_projected(
        self, record: LoopRecord, expected_revision: int,
    ) -> LoopRecord | None:
        return loop_storage.mark_blocker_projected(
            self._connect, record, expected_revision,
        )

    def list_unprojected_blockers(self, limit: int = 100) -> list[LoopRecord]:
        return loop_storage.list_unprojected_blockers(self._connect, limit)

__all__ = ["LoopStorageMixin"]
