"""API-owned activation for accepted Lesson Memory projections."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable

from factory.mcp_utils.interface import get_service

logger = logging.getLogger(__name__)


async def activate_lessons(owner: Any) -> bool:
    loader = get_service("brick_tools")
    if callable(loader):
        loaded = loader("lessons")
        if inspect.isawaitable(loaded):
            await loaded
    runner = get_service("lessons_projection_reconciler")
    if not callable(runner):
        return False
    owner.submit(lessons_loop(runner))
    return True


async def lessons_loop(
    runner: Callable[[], Awaitable[Any]], poll_seconds: float = 30.0,
) -> None:
    while True:
        try:
            await runner()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Lessons projection reconciliation failed: %s", exc)
        await asyncio.sleep(poll_seconds)


__all__ = ["activate_lessons", "lessons_loop"]
