"""API-owned activation for durable Workflow loop reconciliation."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable

from factory.mcp_utils.interface import get_service

logger = logging.getLogger(__name__)


async def activate_workflow_loops(owner: Any) -> bool:
    loader = get_service("brick_tools")
    if callable(loader):
        loaded = loader("workflow")
        if inspect.isawaitable(loaded):
            await loaded
    runner = get_service("workflow_loop_reconciler")
    if not callable(runner):
        return False
    owner.submit(workflow_loop(runner))
    return True


async def workflow_loop(
    runner: Callable[[], Awaitable[Any]], poll_seconds: float = 30.0,
) -> None:
    while True:
        try:
            await runner()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Every edge is durable and is retried on the next bounded pass.
            logger.warning("Workflow loop reconciliation failed: %s", exc)
        await asyncio.sleep(poll_seconds)


__all__ = ["activate_workflow_loops", "workflow_loop"]
