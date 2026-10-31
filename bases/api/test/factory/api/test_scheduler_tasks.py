from __future__ import annotations

import asyncio

import pytest

from factory.api.runtime.scheduler_tasks import scheduler_loop


@pytest.mark.asyncio
async def test_scheduler_loop_runs_immediately_and_retries_after_failure() -> None:
    calls = 0

    async def runner() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")

    task = asyncio.create_task(scheduler_loop(runner, poll_seconds=0.01))
    try:
        for _ in range(20):
            if calls >= 2:
                break
            await asyncio.sleep(0.01)
        assert calls >= 2
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_activate_scheduler_seeds_before_starting_loop(monkeypatch) -> None:
    from factory.api.runtime import scheduler_tasks

    events = []

    async def runner() -> None:
        pass

    def service(name):
        return {
            "brick_tools": lambda brick: events.append(f"load:{brick}"),
            "scheduler_due_runner": runner,
            "scheduler_maintenance_seeder": lambda: events.append("seed"),
        }.get(name)

    class Owner:
        def submit(self, coroutine) -> None:
            events.append("submit")
            coroutine.close()

    monkeypatch.setattr(scheduler_tasks, "get_service", service)
    assert await scheduler_tasks.activate_scheduler(Owner()) is True
    assert events == ["load:scheduler", "seed", "submit"]
