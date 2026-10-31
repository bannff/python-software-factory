from __future__ import annotations

import asyncio

import pytest

from factory.api.runtime.background_tasks import BackgroundTaskOwner


@pytest.mark.asyncio
async def test_background_task_owner_runs_without_os_thread() -> None:
    owner = BackgroundTaskOwner()
    started = asyncio.Event()
    release = asyncio.Event()

    async def work() -> None:
        started.set()
        await release.wait()

    owner.submit(work())
    await asyncio.wait_for(started.wait(), timeout=1)
    release.set()
    await asyncio.sleep(0)
    await owner.close()


@pytest.mark.asyncio
async def test_submit_from_ephemeral_loop_runs_on_the_owning_api_loop() -> None:
    """Reproduce the Scheduler-fire orphan: a drive submitted from inside an
    ``asyncio.run`` on an ``asyncio.to_thread`` worker must still execute.

    Before the fix ``submit`` called ``asyncio.create_task``, binding the
    drive to the ephemeral loop that ``asyncio.run`` tears down on return —
    the drive was cancelled and never ran (run stuck ``running``, no
    checkpoint). The fix binds it to the owning API loop instead.
    """
    owner = BackgroundTaskOwner()
    api_loop = asyncio.get_running_loop()
    ran = asyncio.Event()
    ran_on: dict[str, object] = {}

    async def drive() -> None:
        ran_on["loop"] = asyncio.get_running_loop()
        ran.set()

    def worker() -> None:
        # Mimics fire_dispatch._invoke -> native invoker _run_sync_agent, which
        # runs spawn_background via asyncio.run on this worker thread (no loop).
        async def spawn_like() -> None:
            owner.submit(drive())  # launch_background's fire-and-forget submit
            # returns immediately, exactly like launch_background does

        asyncio.run(spawn_like())

    await asyncio.to_thread(worker)
    await asyncio.wait_for(ran.wait(), timeout=2)
    assert ran_on["loop"] is api_loop
    await owner.close()


@pytest.mark.asyncio
async def test_background_task_owner_cancels_at_shutdown() -> None:
    owner = BackgroundTaskOwner()
    cancelled = asyncio.Event()

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    owner.submit(work())
    await asyncio.sleep(0)
    await owner.close()
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_runtime_lifespan_scopes_background_launcher(monkeypatch) -> None:
    from fastapi import FastAPI
    from factory.agent import interface as agent_interface
    from factory.api.runtime.background_tasks import install_runtime_lifespan
    from factory.mcp_utils.interface import get_service, set_service

    async def close_chat_agent() -> None:
        return None

    monkeypatch.setattr(agent_interface, "close_chat_agent", close_chat_agent)
    previous = get_service("background_task_launcher")
    marker = object()
    set_service("background_task_launcher", marker)
    app = FastAPI()
    install_runtime_lifespan(app)
    try:
        async with app.router.lifespan_context(app):
            assert callable(get_service("background_task_launcher"))
        assert get_service("background_task_launcher") is marker
    finally:
        set_service("background_task_launcher", previous)


@pytest.mark.asyncio
async def test_startup_activates_workflow_recovery() -> None:
    from factory.api.runtime.background_tasks import _activate_recovery
    from factory.mcp_utils.interface import get_service, set_service

    recovered = asyncio.Event()
    previous_loader = get_service("brick_tools")
    previous_reconciler = get_service("workflow_background_reconciler")

    async def work() -> None:
        recovered.set()

    async def load(brick: str) -> None:
        assert brick == "workflow"
        set_service(
            "workflow_background_reconciler",
            lambda submit: (submit(work()), ("run-1",))[1],
        )

    set_service("brick_tools", load)
    owner = BackgroundTaskOwner()
    try:
        assert await _activate_recovery(owner) == ("run-1",)
        await asyncio.wait_for(recovered.wait(), timeout=1)
        await owner.close()
    finally:
        set_service("brick_tools", previous_loader)
        set_service("workflow_background_reconciler", previous_reconciler)
