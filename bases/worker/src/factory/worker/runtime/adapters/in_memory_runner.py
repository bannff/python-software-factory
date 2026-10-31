"""In-memory adapters for agent runner ports — test doubles.

These are the ONLY fakes needed: inbox, clock, persistence.
Real Strands SessionManager is NOT faked — the invoke_fn boundary
is what gets mocked in tests.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

from ..agent_runner_models import AgentRunnerState, InboxMessage
from ..agent_runner_ports import ClockPort, InboxPort, RunnerPersistencePort


class InMemoryInbox:
    """In-memory inbox for testing — satisfies InboxPort."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[InboxMessage]] = defaultdict(asyncio.Queue)

    async def enqueue(self, message: InboxMessage) -> None:
        self._queues[message.agent_id].put_nowait(message)

    async def dequeue(self, agent_id: str) -> InboxMessage | None:
        q = self._queues[agent_id]
        if q.empty():
            return None
        return q.get_nowait()

    async def is_empty(self, agent_id: str) -> bool:
        return self._queues[agent_id].empty()

    async def wait_for_message(self, agent_id: str) -> InboxMessage:
        return await self._queues[agent_id].get()


class FakeClock:
    """Deterministic clock for testing — satisfies ClockPort.

    advance(delta) moves time forward and unblocks any sleep_until
    waiters whose target is now past.
    """

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 0, 0, 0)
        self._waiters: list[tuple[datetime, asyncio.Event]] = []

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        """Advance the clock and wake all due waiters."""
        self._now += delta
        still_waiting = []
        for target, event in self._waiters:
            if target <= self._now:
                event.set()
            else:
                still_waiting.append((target, event))
        self._waiters = still_waiting

    async def sleep_until(self, target: datetime) -> None:
        if target <= self._now:
            return
        event = asyncio.Event()
        self._waiters.append((target, event))
        await event.wait()


class InMemoryPersistence:
    """In-memory persistence for testing — satisfies RunnerPersistencePort."""

    def __init__(self) -> None:
        self._store: dict[str, AgentRunnerState] = {}

    async def save_state(self, state: AgentRunnerState) -> None:
        # Deep copy via reconstruction to prevent aliasing
        self._store[state.agent_id] = AgentRunnerState(
            agent_id=state.agent_id,
            status=state.status,
            auto_wake_at=state.auto_wake_at,
            session_id=state.session_id,
            turn_count=state.turn_count,
            last_active_at=state.last_active_at,
        )

    async def load_state(self, agent_id: str) -> AgentRunnerState | None:
        stored = self._store.get(agent_id)
        if stored is None:
            return None
        return AgentRunnerState(
            agent_id=stored.agent_id,
            status=stored.status,
            auto_wake_at=stored.auto_wake_at,
            session_id=stored.session_id,
            turn_count=stored.turn_count,
            last_active_at=stored.last_active_at,
        )

    async def list_agents(self) -> list[str]:
        return list(self._store.keys())
