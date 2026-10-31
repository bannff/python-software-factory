"""Scheduler runtime composition."""
from __future__ import annotations

import os

from factory.storage.interface import get_sql_store

from .adapters.sql import SQLScheduleStore
from .lifecycle import SchedulerLifecycle
from .models import ScheduleRecord


class SchedulerRuntime:
    def __init__(self, lifecycle: SchedulerLifecycle | None = None) -> None:
        self._lifecycle = lifecycle

    @property
    def lifecycle(self) -> SchedulerLifecycle:
        if self._lifecycle is None:
            path = os.getenv("COMPANION_X_SCHEDULER_DB_PATH", "./.storage/scheduler.db")
            self._lifecycle = SchedulerLifecycle(
                SQLScheduleStore(get_sql_store("sqlite", db_path=path)),
            )
        return self._lifecycle

    @staticmethod
    def health_check() -> dict:
        return {"healthy": True, "backend": "sqlite"}

    async def replay_claimed(self, limit: int = 100) -> tuple[str, ...]:
        from .fire_dispatch import replay_claimed
        return await replay_claimed(self.lifecycle, limit)

    async def tick(self, limit: int = 100) -> tuple[str, ...]:
        from datetime import datetime, timezone
        from .outcome_observer import observe_outcomes
        await self.replay_claimed(limit)
        await observe_outcomes(self.lifecycle, limit)
        self.lifecycle.claim_due(datetime.now(timezone.utc), limit)
        return await self.replay_claimed(limit)

    async def trigger(
        self, tenant_id: str, owner_id: str, schedule_id: str,
        expected_revision: int,
    ):
        from datetime import datetime, timezone
        fire = self.lifecycle.trigger(
            tenant_id, owner_id, schedule_id, expected_revision,
            datetime.now(timezone.utc),
        )
        await self.replay_claimed()
        return self.lifecycle.store.get_fire(
            tenant_id, owner_id, schedule_id, fire.fire_sequence,
        )


_runtime: SchedulerRuntime | None = None


def get_runtime() -> SchedulerRuntime:
    global _runtime
    if _runtime is None:
        _runtime = SchedulerRuntime()
    return _runtime


def ensure_telemetry_retention_schedule(
    runtime: SchedulerRuntime | None = None,
) -> ScheduleRecord:
    """Create or recover the fixed system retention schedule."""
    return (runtime or get_runtime()).lifecycle.create(
        "system", "system", "system-maintenance", "system-maintenance",
        "system-maintenance", "daily telemetry retention", "cron",
        cron_expression="17 3 * * *", timezone_name="UTC",
        strict_schedule=True, delivery_mode="maintenance",
        maintenance_target="telemetry_retention",
        schedule_id="system_telemetry_retention",
    )


__all__ = [
    "SchedulerRuntime", "ensure_telemetry_retention_schedule", "get_runtime",
]

