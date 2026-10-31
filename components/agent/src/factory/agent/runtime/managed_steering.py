"""Process-local locator for live Workflow-managed Agent steering."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _Owner:
    loop: asyncio.AbstractEventLoop
    runtime: Any
    request: Any


class ManagedSteeringRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, _Owner] = {}

    def register(self, run_id: str, runtime: Any, request: Any) -> None:
        with self._lock:
            if run_id in self._active:
                raise RuntimeError("managed steering owner already active")
            self._active[run_id] = _Owner(asyncio.get_running_loop(), runtime, request)

    def unregister(self, run_id: str, runtime: Any) -> None:
        with self._lock:
            owner = self._active.get(run_id)
            if owner is not None and owner.runtime is runtime:
                self._active.pop(run_id, None)

    async def offer(self, run_id: str, send_id: str, content: str) -> Any | None:
        with self._lock:
            owner = self._active.get(run_id)
        if owner is None:
            return None
        work = owner.runtime.offer_steer(owner.request, send_id, content)
        if owner.loop is asyncio.get_running_loop():
            return await work
        future = asyncio.run_coroutine_threadsafe(work, owner.loop)
        return await asyncio.wrap_future(future)


managed_steering = ManagedSteeringRegistry()

__all__ = ["ManagedSteeringRegistry", "managed_steering"]
