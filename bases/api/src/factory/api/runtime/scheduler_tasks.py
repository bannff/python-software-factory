"""API-owned recurring Scheduler activation."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable

from factory.mcp_utils.interface import get_service

logger = logging.getLogger(__name__)


async def activate_scheduler(owner: Any) -> bool:
    loader = get_service("brick_tools")
    if callable(loader):
        loaded = loader("scheduler")
        if inspect.isawaitable(loaded):
            await loaded
    runner = get_service("scheduler_due_runner")
    seeder = get_service("scheduler_maintenance_seeder")
    if not callable(runner) or not callable(seeder):
        return False
    seeder()
    owner.submit(scheduler_loop(runner))
    return True


async def scheduler_loop(
    runner: Callable[[], Awaitable[Any]], poll_seconds: float = 30.0,
) -> None:
    while True:
        try:
            await runner()
        except asyncio.CancelledError:
            raise
        except Exception:
            # The next tick retries; never swallow silently.
            logger.exception("scheduler tick failed")
        await asyncio.sleep(poll_seconds)


__all__ = ["activate_scheduler", "scheduler_loop"]
