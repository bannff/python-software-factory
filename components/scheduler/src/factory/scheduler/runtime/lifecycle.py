"""Owner-scoped Scheduler lifecycle and fire claiming."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .errors import ScheduleConflictError, ScheduleNotFoundError
from .models import FireRecord, ScheduleKind, ScheduleRecord, ScheduleState
from .next_fire import next_fire
from .ports import ScheduleStore


class SchedulerLifecycle:
    def __init__(self, store: ScheduleStore) -> None:
        self.store = store

    def create(
        self, tenant_id: str, owner_id: str, origin_session_id: str,
        origin_thread_id: str, agent_id: str, task: str, kind: str, *,
        interval_seconds: int | None = None,
        one_shot_at: datetime | None = None,
        cron_expression: str | None = None,
        timezone_name: str = "UTC", skip_dates: tuple[str, ...] = (),
        strict_schedule: bool = False,
        output_schema: str | None = None, delivery_mode: str = "origin",
        loop_id: str | None = None, loop_cycle: int | None = None,
        maintenance_target: str | None = None,
        schedule_id: str | None = None,
    ) -> ScheduleRecord:
        now = datetime.now(timezone.utc)
        selected = ScheduleKind(kind)
        interval = max(60, interval_seconds or 0) if selected is ScheduleKind.INTERVAL else None
        fire_at = next_fire(
            selected, created_at=now, interval_seconds=interval,
            one_shot_at=one_shot_at, cron_expression=cron_expression,
            timezone_name=timezone_name, skip_dates=skip_dates,
        )
        return self.store.create(ScheduleRecord(
            tenant_id=tenant_id, owner_id=owner_id,
            schedule_id=schedule_id or f"sch_{uuid4().hex}",
            origin_session_id=origin_session_id, origin_thread_id=origin_thread_id,
            agent_id=agent_id, task=task, kind=selected,
            interval_seconds=interval,
            one_shot_at=one_shot_at if selected is ScheduleKind.ONE_SHOT else None,
            cron_expression=cron_expression if selected is ScheduleKind.CRON else None,
            timezone=timezone_name, skip_dates=skip_dates,
            strict_schedule=strict_schedule,
            output_schema=output_schema, delivery_mode=delivery_mode,
            loop_id=loop_id, loop_cycle=loop_cycle,
            maintenance_target=maintenance_target,
            next_fire_at=fire_at, created_at=now, updated_at=now, revision=1,
        ))

    def get(self, tenant_id: str, owner_id: str, schedule_id: str) -> ScheduleRecord:
        value = self.store.get(tenant_id, owner_id, schedule_id)
        if value is None:
            raise ScheduleNotFoundError
        return value

    def list(self, tenant_id: str, owner_id: str) -> list[ScheduleRecord]:
        return self.store.list(tenant_id, owner_id)

    def pause(
        self, tenant_id: str, owner_id: str, schedule_id: str, revision: int,
    ) -> ScheduleRecord:
        return self._state(
            tenant_id, owner_id, schedule_id, revision, ScheduleState.PAUSED, None,
        )

    def resume(
        self, tenant_id: str, owner_id: str, schedule_id: str, revision: int,
    ) -> ScheduleRecord:
        record = self.get(tenant_id, owner_id, schedule_id)
        if record.state not in {ScheduleState.PAUSED, ScheduleState.AUTO_PAUSED}:
            raise ValueError("only paused schedules can be resumed")
        fire_at = next_fire(
            record.kind, created_at=datetime.now(timezone.utc),
            interval_seconds=record.interval_seconds,
            one_shot_at=record.one_shot_at,
            cron_expression=record.cron_expression,
            timezone_name=record.timezone, skip_dates=record.skip_dates,
            last_fire_at=record.last_fire_at,
        )
        return self._state(
            tenant_id, owner_id, schedule_id, revision,
            ScheduleState.ACTIVE, fire_at.isoformat() if fire_at else None,
        )

    def remove(
        self, tenant_id: str, owner_id: str, schedule_id: str, revision: int,
    ) -> None:
        if self.store.remove(tenant_id, owner_id, schedule_id, revision):
            return
        self.get(tenant_id, owner_id, schedule_id)
        raise ScheduleConflictError

    def claim(self, record: ScheduleRecord, fired_at: datetime) -> tuple[ScheduleRecord, FireRecord]:
        sequence = record.fire_sequence + 1
        if self.store.has_nonterminal(
            record.tenant_id, record.owner_id, record.schedule_id,
        ):
            raise ScheduleConflictError
        launch_id = f"sched_{record.schedule_id}_{sequence}"
        now = fired_at.astimezone(timezone.utc)
        fire = self.store.create_fire(FireRecord(
            tenant_id=record.tenant_id, owner_id=record.owner_id,
            schedule_id=record.schedule_id, fire_sequence=sequence,
            launch_id=launch_id, created_at=now, updated_at=now, revision=1,
        ))
        completed = record.kind is ScheduleKind.ONE_SHOT
        next_at = None if completed else next_fire(
            record.kind, created_at=record.created_at,
            interval_seconds=record.interval_seconds,
            cron_expression=record.cron_expression,
            timezone_name=record.timezone, skip_dates=record.skip_dates,
            last_fire_at=(record.next_fire_at if record.strict_schedule
                          and record.next_fire_at is not None else now),
        ).isoformat()
        updated = self.store.advance_claim(
            record, sequence, next_at,
            ScheduleState.COMPLETED if completed else ScheduleState.ACTIVE,
            now.isoformat(),
        )
        if updated is None:
            raise ScheduleConflictError
        return updated, fire

    def claim_due(
        self, fired_at: datetime, limit: int = 100,
    ) -> tuple[FireRecord, ...]:
        claimed = []
        for record in self.store.list_due(
            fired_at.astimezone(timezone.utc).isoformat(), limit,
        ):
            try:
                _, fire = self.claim(record, fired_at)
                claimed.append(fire)
            except ScheduleConflictError:
                continue
        return tuple(claimed)


    def trigger(
        self, tenant_id: str, owner_id: str, schedule_id: str,
        expected_revision: int, fired_at: datetime,
    ) -> FireRecord:
        record = self.get(tenant_id, owner_id, schedule_id)
        if record.revision != expected_revision or record.state is not ScheduleState.ACTIVE:
            raise ScheduleConflictError
        _, fire = self.claim(record, fired_at)
        return fire
    def _state(self, tenant_id: str, owner_id: str, schedule_id: str,
               revision: int, state: ScheduleState,
               next_fire_at: str | None) -> ScheduleRecord:
        value = self.store.set_state(
            tenant_id, owner_id, schedule_id, state, revision, next_fire_at,
        )
        if value is not None:
            return value
        self.get(tenant_id, owner_id, schedule_id)
        raise ScheduleConflictError


__all__ = ["SchedulerLifecycle"]
