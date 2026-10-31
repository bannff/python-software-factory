"""Process-local cancellation ownership for Workflow-managed graphs."""
from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

CancelOutcome = Literal[
    "cancel_requested", "already_requested", "not_owner", "not_found",
]
Key = tuple[str, str, int, str]


@dataclass(frozen=True)
class _Owner:
    loop: asyncio.AbstractEventLoop
    task: asyncio.Task[object]


class ManagedCancellationRegistry:
    """Own exact attempt-revision tasks and bounded cancellation tombstones."""

    def __init__(self, *, max_tombstones: int = 1024, ttl_seconds: float = 300.0):
        if max_tombstones < 1 or ttl_seconds <= 0:
            raise ValueError("cancellation bounds must be positive")
        self._max, self._ttl = max_tombstones, ttl_seconds
        self._lock = threading.Lock()
        self._active: dict[Key, _Owner] = {}
        self._requested: OrderedDict[Key, float] = OrderedDict()
        self._finished: OrderedDict[Key, float] = OrderedDict()

    @staticmethod
    def _key(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str,
    ) -> Key:
        return workflow_run_id, attempt_id, revision, manifest_digest

    def _purge(self, now: float) -> None:
        for tombstones in (self._requested, self._finished):
            while tombstones:
                key, expires = next(iter(tombstones.items()))
                if expires > now and len(tombstones) <= self._max:
                    break
                tombstones.pop(key, None)

    def _remember(self, values: OrderedDict[Key, float], key: Key, now: float) -> None:
        values[key] = now + self._ttl
        values.move_to_end(key)
        self._purge(now)

    def register(
        self, *, workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, loop: asyncio.AbstractEventLoop,
        task: asyncio.Task[object],
    ) -> None:
        key = self._key(workflow_run_id, attempt_id, revision, manifest_digest)
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            if key in self._active:
                raise RuntimeError("managed graph attempt is already active")
            if any(active[:2] == key[:2] for active in self._active):
                raise RuntimeError("another managed graph attempt revision is active")
            self._finished.pop(key, None)
            self._active[key] = _Owner(loop=loop, task=task)
            requested = key in self._requested
        if requested:
            loop.call_soon_threadsafe(task.cancel)

    def unregister(self, *, key: Key, task: asyncio.Task[object]) -> None:
        with self._lock:
            owner = self._active.get(key)
            if owner is None or owner.task is not task:
                return
            del self._active[key]
            self._remember(self._finished, key, time.monotonic())

    def cancel(
        self, *, workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str,
    ) -> CancelOutcome:
        key = self._key(workflow_run_id, attempt_id, revision, manifest_digest)
        owner: _Owner | None = None
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            if key in self._requested:
                self._requested.move_to_end(key)
                return "already_requested"
            owner = self._active.get(key)
            if owner is not None:
                self._remember(self._requested, key, now)
            elif any(active[0] == workflow_run_id for active in self._active):
                return "not_owner"
            elif key in self._finished:
                self._finished.move_to_end(key)
                return "not_found"
            else:
                self._remember(self._requested, key, now)
        if owner is not None:
            owner.loop.call_soon_threadsafe(owner.task.cancel)
        return "cancel_requested"


__all__ = ["CancelOutcome", "Key", "ManagedCancellationRegistry"]
