"""SQLStore adapter for owner-scoped schedules and unique fire records."""
from __future__ import annotations

from factory.storage.interface import SQLStore

from ..models import FireRecord, FireState, ScheduleRecord, ScheduleState
from .sql_schedule_ops import create_schedule, initialize
from .sql_rows import (
    FIRE_FIELDS, fire_from, params, schedule_from,
)


class SQLScheduleStore:
    def __init__(self, sql: SQLStore) -> None:
        self._sql = sql
        initialize(sql)

    def create(self, record: ScheduleRecord) -> ScheduleRecord:
        return create_schedule(record, self._insert, self.get)

    def get(
        self, tenant_id: str, owner_id: str, schedule_id: str,
    ) -> ScheduleRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM scheduler_schedules WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id",
            _identity(tenant_id, owner_id, schedule_id),
        )
        return schedule_from(row)

    def list(self, tenant_id: str, owner_id: str) -> list[ScheduleRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM scheduler_schedules WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id ORDER BY created_at,schedule_id",
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        return [item for row in rows if (item := schedule_from(row)) is not None]

    def set_state(
        self, tenant_id: str, owner_id: str, schedule_id: str,
        state: ScheduleState, expected_revision: int, next_fire_at: str | None,
    ) -> ScheduleRecord | None:
        result = self._sql.execute(
            "UPDATE scheduler_schedules SET state=:state,next_fire_at=:next_fire_at,"
            "consecutive_failures=CASE WHEN :state='active' THEN 0 "
            "ELSE consecutive_failures END,updated_at=:updated_at,revision=revision+1 "
            "WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND revision=:expected_revision",
            {**_identity(tenant_id, owner_id, schedule_id), "state": state.value,
             "next_fire_at": next_fire_at, "updated_at": _now(),
             "expected_revision": expected_revision},
        )
        return self.get(tenant_id, owner_id, schedule_id) if result.row_count == 1 else None

    def remove(
        self, tenant_id: str, owner_id: str, schedule_id: str,
        expected_revision: int,
    ) -> bool:
        result = self._sql.execute(
            "DELETE FROM scheduler_schedules WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND revision=:expected_revision",
            {**_identity(tenant_id, owner_id, schedule_id),
             "expected_revision": expected_revision},
        )
        return result.row_count == 1

    def advance_claim(
        self, record: ScheduleRecord, fire_sequence: int,
        next_fire_at: str | None, state: ScheduleState, fired_at: str,
    ) -> ScheduleRecord | None:
        result = self._sql.execute(
            "UPDATE scheduler_schedules SET fire_sequence=:fire_sequence,"
            "last_fire_at=:fired_at,next_fire_at=:next_fire_at,state=:state,"
            "updated_at=:fired_at,revision=revision+1 WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id AND revision=:revision",
            {**_identity(record.tenant_id, record.owner_id, record.schedule_id),
             "fire_sequence": fire_sequence, "fired_at": fired_at,
             "next_fire_at": next_fire_at, "state": state.value,
             "revision": record.revision},
        )
        return self.get(
            record.tenant_id, record.owner_id, record.schedule_id,
        ) if result.row_count == 1 else None

    def create_fire(self, record: FireRecord) -> FireRecord:
        try:
            self._insert("scheduler_fires", FIRE_FIELDS, params(record))
            return record
        except Exception:
            existing = self.get_fire(
                record.tenant_id, record.owner_id,
                record.schedule_id, record.fire_sequence,
            )
            if existing == record:
                return existing
            raise
    def has_nonterminal(self, tenant_id: str, owner_id: str, schedule_id: str) -> bool:
        row = self._sql.fetch_one(
            "SELECT 1 AS present FROM scheduler_fires WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND state IN ('claimed','enrolled') LIMIT 1",
            _identity(tenant_id, owner_id, schedule_id),
        )
        return row is not None


    def get_fire(
        self, tenant_id: str, owner_id: str, schedule_id: str,
        fire_sequence: int,
    ) -> FireRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM scheduler_fires WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND fire_sequence=:fire_sequence",
            {**_identity(tenant_id, owner_id, schedule_id),
             "fire_sequence": fire_sequence},
        )
        return fire_from(row)

    def list_due(self, now: str, limit: int = 100) -> list[ScheduleRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM scheduler_schedules WHERE state='active' "
            "AND next_fire_at IS NOT NULL AND next_fire_at<=:now "
            "ORDER BY next_fire_at,schedule_id LIMIT :limit",
            {"now": now, "limit": max(1, min(limit, 1000))},
        )
        return [item for row in rows if (item := schedule_from(row)) is not None]


    def list_claimed(self, limit: int = 100) -> list[FireRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM scheduler_fires WHERE state='claimed' "
            "ORDER BY created_at,schedule_id,fire_sequence LIMIT :limit",
            {"limit": max(1, min(limit, 1000))},
        )
        return [item for row in rows if (item := fire_from(row)) is not None]

    def mark_enrolled(
        self, fire: FireRecord, workflow_run_id: str, expected_revision: int,
    ) -> FireRecord | None:
        result = self._sql.execute(
            "UPDATE scheduler_fires SET state='enrolled',workflow_run_id=:run_id,"
            "updated_at=:updated_at,revision=revision+1 WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND fire_sequence=:fire_sequence AND revision=:revision AND state='claimed'",
            {**_identity(fire.tenant_id, fire.owner_id, fire.schedule_id),
             "fire_sequence": fire.fire_sequence, "run_id": workflow_run_id,
             "updated_at": _now(), "revision": expected_revision},
        )
        return self.get_fire(
            fire.tenant_id, fire.owner_id, fire.schedule_id, fire.fire_sequence,
        ) if result.row_count == 1 else None

    def list_enrolled(self, limit: int = 100) -> list[FireRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM scheduler_fires WHERE state='enrolled' ORDER BY updated_at LIMIT :limit",
            {"limit": max(1, min(limit, 1000))},
        )
        return [item for row in rows if (item := fire_from(row)) is not None]

    def mark_outcome(
        self, fire: FireRecord, state: FireState, expected_revision: int,
    ) -> FireRecord | None:
        if state not in {FireState.SUCCEEDED, FireState.FAILED, FireState.CANCELLED}:
            raise ValueError("fire outcome must be terminal")
        result = self._sql.execute(
            "UPDATE scheduler_fires SET state=:state,updated_at=:updated_at,revision=revision+1 "
            "WHERE tenant_id=:tenant_id AND owner_id=:owner_id AND schedule_id=:schedule_id "
            "AND fire_sequence=:fire_sequence AND revision=:revision AND state='enrolled'",
            {**_identity(fire.tenant_id, fire.owner_id, fire.schedule_id),
             "fire_sequence": fire.fire_sequence, "revision": expected_revision,
             "state": state.value, "updated_at": _now()},
        )
        return self.get_fire(
            fire.tenant_id, fire.owner_id, fire.schedule_id, fire.fire_sequence,
        ) if result.row_count == 1 else None

    def _insert(self, table: str, fields: tuple[str, ...], values: dict) -> None:
        columns = ",".join(fields)
        bind = ",".join(f":{field}" for field in fields)
        self._sql.execute(f"INSERT INTO {table} ({columns}) VALUES ({bind})", values)


def _identity(tenant_id: str, owner_id: str, schedule_id: str) -> dict[str, str]:
    return {"tenant_id": tenant_id, "owner_id": owner_id, "schedule_id": schedule_id}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


__all__ = ["SQLScheduleStore"]
