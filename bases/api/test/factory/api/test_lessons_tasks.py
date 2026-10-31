from __future__ import annotations

import asyncio

import pytest

from factory.api.runtime.background_tasks import BackgroundTaskOwner
from factory.api.runtime.lessons_tasks import activate_lessons, lessons_loop
from factory.mcp_utils.interface import get_service, set_service


@pytest.mark.asyncio
async def test_lessons_loop_runs_immediately_and_retries() -> None:
    calls = 0

    async def runner() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")

    task = asyncio.create_task(lessons_loop(runner, poll_seconds=0.01))
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
async def test_lessons_activation_uses_background_task_owner() -> None:
    calls = 0

    async def runner() -> None:
        nonlocal calls
        calls += 1

    previous_runner = get_service("lessons_projection_reconciler")
    previous_loader = get_service("brick_tools")
    set_service("lessons_projection_reconciler", runner)
    set_service("brick_tools", lambda name: None)
    owner = BackgroundTaskOwner()
    try:
        assert await activate_lessons(owner)
        for _ in range(20):
            if calls:
                break
            await asyncio.sleep(0.01)
        assert calls == 1
    finally:
        await owner.close()
        set_service("lessons_projection_reconciler", previous_runner)
        set_service("brick_tools", previous_loader)
