"""Thread → live-invocation-task registry, so an external caller that only
knows a ``thread_id`` (e.g. ``session_stop``) can cancel a running turn without
needing the random per-turn ``invocation_id``."""
from __future__ import annotations

import asyncio


class ActiveThreadRegistry:
    """Cooperative cancellation index: thread_id -> {invocation_id, ...}."""

    def __init__(self) -> None:
        self._by_thread: dict[str, set[str]] = {}

    def track(self, thread_id: str | None, invocation_id: str) -> None:
        if thread_id:
            self._by_thread.setdefault(thread_id, set()).add(invocation_id)

    def untrack(self, thread_id: str | None, invocation_id: str) -> None:
        if not thread_id or thread_id not in self._by_thread:
            return
        self._by_thread[thread_id].discard(invocation_id)
        if not self._by_thread[thread_id]:
            del self._by_thread[thread_id]

    def invocations_for(self, thread_id: str) -> frozenset[str]:
        return frozenset(self._by_thread.get(thread_id, ()))

    def __contains__(self, thread_id: str) -> bool:
        return thread_id in self._by_thread

    def cancel_all(self, thread_id: str, active: dict[str, asyncio.Task]) -> bool:
        """Cancel every live task tracked for this thread; True if any were cancelled."""
        cancelled = False
        for invocation_id in list(self.invocations_for(thread_id)):
            task = active.get(invocation_id)
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                cancelled = True
        return cancelled


async def cancel_and_drain(active: dict[str, asyncio.Task]) -> None:
    """Cancel every task not the caller's own, then await them all to settle."""
    tasks = [task for task in active.values() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    active.clear()


__all__ = ["ActiveThreadRegistry", "cancel_and_drain"]
