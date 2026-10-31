from __future__ import annotations

import tempfile
from datetime import datetime, timezone

from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.errors import ScheduleConflictError
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.storage.interface import StorageRuntime


class SchedulerMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.temp = tempfile.TemporaryDirectory()
        sql = StorageRuntime().get_sql_store(
            "sqlite", db_path=f"{self.temp.name}/scheduler.db",
        )
        self.runtime = SchedulerLifecycle(SQLScheduleStore(sql))
        self.record = self.runtime.create(
            "tenant", "owner", "session", "thread", "developer", "work",
            "interval", interval_seconds=60, schedule_id="property_job",
        )
        self.sequences: list[int] = []

    @rule()
    def pause_or_resume(self) -> None:
        if self.record.state.value == "active":
            self.record = self.runtime.pause(
                "tenant", "owner", self.record.schedule_id, self.record.revision,
            )
        else:
            self.record = self.runtime.resume(
                "tenant", "owner", self.record.schedule_id, self.record.revision,
            )

    @rule()
    def claim_when_active(self) -> None:
        if self.record.state.value != "active":
            return
        if self.runtime.store.has_nonterminal("tenant", "owner", self.record.schedule_id):
            try:
                self.runtime.claim(self.record, datetime.now(timezone.utc))
            except ScheduleConflictError:
                return
            raise AssertionError("overlapping claim was accepted")
        self.record, fire = self.runtime.claim(
            self.record, datetime.now(timezone.utc),
        )
        self.sequences.append(fire.fire_sequence)

    @rule()
    def stale_revision_never_mutates(self) -> None:
        if self.record.revision <= 1:
            return
        before = self.runtime.get("tenant", "owner", self.record.schedule_id)
        try:
            self.runtime.pause(
                "tenant", "owner", self.record.schedule_id,
                self.record.revision - 1,
            )
        except ScheduleConflictError:
            pass
        after = self.runtime.get("tenant", "owner", self.record.schedule_id)
        assert after == before

    @invariant()
    def fire_sequences_are_unique_and_monotonic(self) -> None:
        assert self.sequences == sorted(set(self.sequences))
        assert self.record.fire_sequence == len(self.sequences)

    def teardown(self) -> None:
        self.temp.cleanup()


TestSchedulerMachine = SchedulerMachine.TestCase
