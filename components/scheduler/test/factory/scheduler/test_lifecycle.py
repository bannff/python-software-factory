from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.errors import ScheduleConflictError
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.scheduler.runtime.models import FireRecord, FireState
from factory.storage.interface import StorageRuntime


def _runtime(path: str) -> SchedulerLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=path)
    return SchedulerLifecycle(SQLScheduleStore(sql))


def _create(runtime: SchedulerLifecycle, **changes):
    values = dict(
        tenant_id="tenant", owner_id="owner", origin_session_id="session",
        origin_thread_id="thread", agent_id="developer", task="do work",
        kind="interval", interval_seconds=30, schedule_id="daily_job",
    )
    values.update(changes)
    return runtime.create(**values)


def test_interval_floor_pause_resume_and_revision_cas(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "db.sqlite"))
    record = _create(runtime)
    assert record.interval_seconds == 60
    paused = runtime.pause("tenant", "owner", record.schedule_id, 1)
    assert paused.state.value == "paused" and paused.next_fire_at is None
    with pytest.raises(ScheduleConflictError):
        runtime.resume("tenant", "owner", record.schedule_id, 1)
    resumed = runtime.resume("tenant", "owner", record.schedule_id, 2)
    assert resumed.state.value == "active" and resumed.revision == 3


def test_one_shot_claim_completes_and_survives_restart(tmp_path) -> None:
    path = str(tmp_path / "restart.sqlite")
    runtime = _runtime(path)
    when = datetime.now(timezone.utc) + timedelta(minutes=5)
    record = _create(
        runtime, kind="one_shot", interval_seconds=None,
        one_shot_at=when, schedule_id="one_shot",
    )
    updated, fire = runtime.claim(record, when)
    assert updated.state.value == "completed" and updated.next_fire_at is None
    assert fire.launch_id == "sched_one_shot_1"
    restarted = _runtime(path)
    assert restarted.get("tenant", "owner", "one_shot") == updated
    assert restarted.store.get_fire("tenant", "owner", "one_shot", 1) == fire


def test_owner_scope_remove_and_fire_uniqueness(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "scope.sqlite"))
    record = _create(runtime)
    assert runtime.store.get("tenant", "other", record.schedule_id) is None
    now = datetime.now(timezone.utc)
    fire = FireRecord(
        tenant_id="tenant", owner_id="owner", schedule_id=record.schedule_id,
        fire_sequence=1, launch_id="sched_daily_job_1",
        created_at=now, updated_at=now, revision=1,
    )
    assert runtime.store.create_fire(fire) == fire
    assert runtime.store.create_fire(fire) == fire
    runtime.remove("tenant", "owner", record.schedule_id, 1)
    assert runtime.store.get("tenant", "owner", record.schedule_id) is None


def test_schedule_id_bounds_and_kind_exclusivity(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "validation.sqlite"))
    with pytest.raises(ValidationError):
        _create(runtime, schedule_id="bad:id")
    with pytest.raises((ValidationError, ValueError)):
        _create(runtime, kind="one_shot", one_shot_at=None, interval_seconds=60)


def test_fire_outcomes_reset_and_auto_pause_atomically(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "outcomes.sqlite"))
    record = _create(runtime, schedule_id="failures")
    for expected in range(1, 6):
        record, fire = runtime.claim(record, datetime.now(timezone.utc))
        enrolled = runtime.store.mark_enrolled(fire, f"run-{expected}", fire.revision)
        runtime.store.mark_outcome(enrolled, FireState.FAILED, enrolled.revision)
        record = runtime.get("tenant", "owner", "failures")
        assert record.consecutive_failures == expected
    assert record.state.value == "auto_paused" and record.next_fire_at is None

    success = _create(runtime, schedule_id="success")
    success, fire = runtime.claim(success, datetime.now(timezone.utc))
    enrolled = runtime.store.mark_enrolled(fire, "run-ok", fire.revision)
    runtime.store.mark_outcome(enrolled, FireState.SUCCEEDED, enrolled.revision)
    success = runtime.get("tenant", "owner", "success")
    assert success.consecutive_failures == 0


def test_nonterminal_fire_blocks_overlap(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "overlap.sqlite"))
    record = _create(runtime, schedule_id="overlap")
    updated, _ = runtime.claim(record, datetime.now(timezone.utc))
    with pytest.raises(ScheduleConflictError):
        runtime.claim(updated, datetime.now(timezone.utc) + timedelta(minutes=2))
    assert runtime.store.get_fire("tenant", "owner", "overlap", 2) is None


def test_completed_cannot_resume_and_auto_pause_resume_resets_failures(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "resume.sqlite"))
    when = datetime.now(timezone.utc) + timedelta(minutes=1)
    one = _create(runtime, kind="one_shot", interval_seconds=None,
                  one_shot_at=when, schedule_id="once")
    completed, _ = runtime.claim(one, when)
    with pytest.raises(ValueError, match="only paused"):
        runtime.resume("tenant", "owner", "once", completed.revision)

    record = _create(runtime, schedule_id="retry")
    for sequence in range(1, 6):
        record, fire = runtime.claim(record, when + timedelta(minutes=sequence))
        enrolled = runtime.store.mark_enrolled(fire, f"run-{sequence}", fire.revision)
        runtime.store.mark_outcome(enrolled, FireState.FAILED, enrolled.revision)
        record = runtime.get("tenant", "owner", "retry")
    resumed = runtime.resume("tenant", "owner", "retry", record.revision)
    assert resumed.consecutive_failures == 0


def test_strict_schedule_advances_from_nominal_fire_time(tmp_path) -> None:
    runtime = _runtime(str(tmp_path / "strict.sqlite"))
    record = _create(runtime, schedule_id="strict", strict_schedule=True)
    nominal = record.next_fire_at
    fired_late = nominal + timedelta(minutes=10)
    updated, _ = runtime.claim(record, fired_late)
    assert updated.next_fire_at == nominal + timedelta(seconds=60)
