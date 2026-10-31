"""Scheduler SQL initialization and replay-safe schedule creation."""
from __future__ import annotations

from typing import Any, Callable

from ..models import ScheduleRecord
from .sql_rows import (
    FIRE_SCHEMA, OUTCOME_TRIGGERS, SCHEDULE_FIELDS, SCHEDULE_MIGRATIONS,
    SCHEDULE_SCHEMA, params, same_schedule_spec,
)


def initialize(sql: Any) -> None:
    sql.execute(SCHEDULE_SCHEMA)
    columns = {row["name"] for row in sql.fetch_all(
        "PRAGMA table_info(scheduler_schedules)",
    )}
    for statement in SCHEDULE_MIGRATIONS:
        if statement.split(" COLUMN ", 1)[1].split()[0] not in columns:
            sql.execute(statement)
    sql.execute(FIRE_SCHEMA)
    for trigger in OUTCOME_TRIGGERS:
        sql.execute(trigger)


def create_schedule(
    record: ScheduleRecord, insert: Callable[..., None],
    get: Callable[..., ScheduleRecord | None],
) -> ScheduleRecord:
    try:
        insert("scheduler_schedules", SCHEDULE_FIELDS, params(record))
        return record
    except Exception:
        existing = get(record.tenant_id, record.owner_id, record.schedule_id)
        if existing is not None and same_schedule_spec(existing, record):
            return existing
        raise


__all__ = ["create_schedule", "initialize"]
