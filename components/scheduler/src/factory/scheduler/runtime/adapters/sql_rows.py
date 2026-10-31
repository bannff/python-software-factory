"""Scheduler SQL schemas and strict row projections."""
from __future__ import annotations

from typing import Any

from ..models import FireRecord, ScheduleRecord

SCHEDULE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_schedules (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, schedule_id TEXT NOT NULL,
 origin_session_id TEXT NOT NULL, origin_thread_id TEXT NOT NULL,
 agent_id TEXT NOT NULL, task TEXT NOT NULL, kind TEXT NOT NULL,
 interval_seconds INTEGER, one_shot_at TEXT, cron_expression TEXT,
 timezone TEXT NOT NULL, skip_dates TEXT NOT NULL, strict_schedule INTEGER NOT NULL,
 output_schema TEXT, delivery_mode TEXT NOT NULL DEFAULT 'origin',
 loop_id TEXT, loop_cycle INTEGER, maintenance_target TEXT,
 state TEXT NOT NULL, next_fire_at TEXT, last_fire_at TEXT,
 fire_sequence INTEGER NOT NULL, consecutive_failures INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL,
 PRIMARY KEY (tenant_id,owner_id,schedule_id)
)
"""
FIRE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_fires (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, schedule_id TEXT NOT NULL,
 fire_sequence INTEGER NOT NULL, launch_id TEXT NOT NULL, state TEXT NOT NULL,
 workflow_run_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 revision INTEGER NOT NULL,
 PRIMARY KEY (tenant_id,owner_id,schedule_id,fire_sequence), UNIQUE(launch_id)
)
"""
SCHEDULE_FIELDS = tuple(ScheduleRecord.model_fields)
FIRE_FIELDS = tuple(FireRecord.model_fields)

OUTCOME_TRIGGERS = (
"""CREATE TRIGGER IF NOT EXISTS scheduler_fire_failed AFTER UPDATE OF state ON scheduler_fires
WHEN OLD.state='enrolled' AND NEW.state='failed' BEGIN
 UPDATE scheduler_schedules SET consecutive_failures=consecutive_failures+1,
 state=CASE WHEN consecutive_failures+1>=5 THEN 'auto_paused' ELSE state END,
 next_fire_at=CASE WHEN consecutive_failures+1>=5 THEN NULL ELSE next_fire_at END,
 revision=revision+1,updated_at=NEW.updated_at
 WHERE tenant_id=NEW.tenant_id AND owner_id=NEW.owner_id AND schedule_id=NEW.schedule_id;
END""",
"""CREATE TRIGGER IF NOT EXISTS scheduler_fire_succeeded AFTER UPDATE OF state ON scheduler_fires
WHEN OLD.state='enrolled' AND NEW.state='succeeded' BEGIN
 UPDATE scheduler_schedules SET consecutive_failures=0,revision=revision+1,updated_at=NEW.updated_at
 WHERE tenant_id=NEW.tenant_id AND owner_id=NEW.owner_id AND schedule_id=NEW.schedule_id;
END""",
)

SCHEDULE_MIGRATIONS = (
    "ALTER TABLE scheduler_schedules ADD COLUMN output_schema TEXT",
    "ALTER TABLE scheduler_schedules ADD COLUMN delivery_mode TEXT NOT NULL DEFAULT 'origin'",
    "ALTER TABLE scheduler_schedules ADD COLUMN loop_id TEXT",
    "ALTER TABLE scheduler_schedules ADD COLUMN loop_cycle INTEGER",
    "ALTER TABLE scheduler_schedules ADD COLUMN maintenance_target TEXT",
)


def params(model: ScheduleRecord | FireRecord) -> dict[str, Any]:
    values = model.model_dump(mode="json")
    values["skip_dates"] = ",".join(values.get("skip_dates", ()))
    return values


def schedule_from(row: dict[str, Any] | None) -> ScheduleRecord | None:
    if row is None:
        return None
    value = dict(row)
    value["skip_dates"] = tuple(filter(None, value.get("skip_dates", "").split(",")))
    return ScheduleRecord.model_validate(value)


def fire_from(row: dict[str, Any] | None) -> FireRecord | None:
    return FireRecord.model_validate(row) if row else None


def same_schedule_spec(left: ScheduleRecord, right: ScheduleRecord) -> bool:
    mutable = {
        "state", "next_fire_at", "last_fire_at", "fire_sequence",
        "consecutive_failures", "created_at", "updated_at", "revision",
    }
    return left.model_dump(exclude=mutable) == right.model_dump(exclude=mutable)


__all__ = [
    "FIRE_FIELDS", "FIRE_SCHEMA", "SCHEDULE_FIELDS", "SCHEDULE_MIGRATIONS",
    "SCHEDULE_SCHEMA",
    "fire_from", "params", "same_schedule_spec", "schedule_from",
]
