"""API lifespan ownership for deferred Workflow drive tasks."""
from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from typing import Any, Coroutine

from factory.mcp_utils.interface import get_service, set_service

logger = logging.getLogger(__name__)


class BackgroundTaskOwner:
    """Hold strong task references and cancel them at application shutdown."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def submit(self, work: Coroutine[Any, Any, Any]) -> None:
        """Bind the drive task to the persistent API loop, not the caller's.

        Deferred drives are submitted from off-loop threads — notably the
        Scheduler fire path, which runs ``spawn_background`` via
        ``asyncio.to_thread`` → the native invoker's ``asyncio.run`` on an
        *ephemeral* loop. Creating the task on that ephemeral loop orphans it:
        ``asyncio.run`` cancels it during teardown before it ever drives the
        run, so the enrolled attempt stays ``running`` forever with no
        checkpoint. Always create the task on the owning API loop instead.
        """
        loop = self._loop
        if loop is None:
            loop = self._loop = asyncio.get_event_loop()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._create(work)
        else:
            loop.call_soon_threadsafe(self._create, work)

    def _create(self, work: Coroutine[Any, Any, Any]) -> None:
        task = self._loop.create_task(work, name="workflow-background-drive")
        self._tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("background Workflow drive failed: %s", error)

    async def close(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


async def _activate_recovery(owner: BackgroundTaskOwner) -> tuple[str, ...]:
    loader = get_service("brick_tools")
    if callable(loader):
        loaded = loader("workflow")
        if inspect.isawaitable(loaded):
            await loaded
    reconcile = get_service("workflow_background_reconciler")
    if not callable(reconcile):
        return ()
    values = reconcile(owner.submit)
    return tuple(values) if values else ()


def install_runtime_lifespan(app: Any) -> None:
    """Compose task ownership and Agent shutdown around the current lifespan."""
    original = app.router.lifespan_context

    @asynccontextmanager
    async def runtime_lifespan(active_app: Any):
        owner = BackgroundTaskOwner()
        previous = get_service("background_task_launcher")
        set_service("background_task_launcher", owner.submit)
        try:
            async with original(active_app):
                await _activate_recovery(owner)
                from .scheduler_tasks import activate_scheduler
                from .workflow_loop_tasks import activate_workflow_loops
                from .lessons_tasks import activate_lessons
                from .terminal_tasks import activate_terminal_reaper
                from .connections_tasks import activate_connections
                await activate_scheduler(owner)
                await activate_workflow_loops(owner)
                await activate_lessons(owner)
                await activate_terminal_reaper(owner)
                await activate_connections(owner)
                yield
        finally:
            await owner.close()
            from .terminal_tasks import close_terminal_runtime
            await close_terminal_runtime()
            set_service("background_task_launcher", previous)
            from factory.agent.interface import close_chat_agent
            await close_chat_agent()

    app.router.lifespan_context = runtime_lifespan


__all__ = ["BackgroundTaskOwner", "install_runtime_lifespan"]
