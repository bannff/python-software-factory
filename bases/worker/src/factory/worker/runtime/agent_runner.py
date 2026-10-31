"""AgentRunner — supervised long-lived runner loop.

One runner per named agent. Lifecycle:
  park → wake (inbox msg OR timer due) → drain ONE message → invoke Strands
  → persist → park.

Uses ONLY verified Strands extension points:
- SessionManager (FileSessionManager) for working history persistence
- SummarizingConversationManager for compaction
- HookProvider / MessageAddedEvent for append-only archive
- Agent(session_manager=..., conversation_manager=..., hooks=[...])
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

from .agent_runner_models import AgentRunnerState, InboxMessage, RunnerStatus
from .agent_runner_ports import ClockPort, InboxPort, RunnerPersistencePort

logger = logging.getLogger(__name__)


class AgentRunner:
    """Supervised loop for a single named agent.

    Functional core: all side effects flow through injected ports.
    The runner does NOT import Strands directly — it receives
    an `invoke_fn` (the model turn) as a constructor arg, keeping
    the runner testable without a live model.
    """

    def __init__(
        self,
        agent_id: str,
        inbox: InboxPort,
        clock: ClockPort,
        persistence: RunnerPersistencePort,
        invoke_fn: Callable[[str, str], Any],
        *,
        auto_wake_at: Any | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._inbox = inbox
        self._clock = clock
        self._persistence = persistence
        self._invoke_fn = invoke_fn
        self._state = AgentRunnerState(
            agent_id=agent_id,
            auto_wake_at=auto_wake_at,
        )
        self._running = False
        self._wake_event = asyncio.Event()

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def state(self) -> AgentRunnerState:
        return self._state

    @property
    def is_parked(self) -> bool:
        return self._state.status == RunnerStatus.PARKED

    async def restore(self) -> None:
        """Restore state from persistence (call on startup/restart)."""
        saved = await self._persistence.load_state(self._agent_id)
        if saved is not None:
            self._state = saved
            logger.info("restored runner state for %s (turns=%d)", self._agent_id, saved.turn_count)

    async def start(self) -> None:
        """Enter the supervised loop. Runs until stop() is called."""
        self._running = True
        await self._park()

        while self._running:
            # Wait for a wake signal: inbox message or timer
            reason = await self._wait_for_wake()
            if not self._running:
                break

            if reason == "timer_due":
                # Consume the one-shot timer. If left set, `auto_wake_at <= now`
                # stays true and `_wait_for_wake` keeps taking its early no-`await`
                # return path — the loop then spins with no suspension point and
                # starves the event loop (the parked agent never yields). A
                # recurring schedule is re-armed by the agent's turn, not here.
                self._state.auto_wake_at = None

            # Drain exactly ONE message per wake
            msg = await self._inbox.dequeue(self._agent_id)
            if msg is None:
                # Timer wake with empty inbox — re-park
                await self._park()
                continue

            # Run one Strands turn
            await self._run_turn(msg)

            # Persist and re-park
            await self._persist()
            await self._park()

    def stop(self) -> None:
        """Signal the runner to exit its loop."""
        self._running = False
        self._wake_event.set()

    def wake(self) -> None:
        """Signal the runner to wake (e.g. inbox enqueue notification)."""
        self._wake_event.set()

    async def _park(self) -> None:
        """Transition to parked state — zero tokens consumed."""
        self._state.status = RunnerStatus.PARKED
        self._wake_event.clear()
        logger.debug("agent %s parked", self._agent_id)

    async def _wait_for_wake(self) -> str:
        """Block until a wake condition fires. Returns reason string."""
        # Two wake sources: inbox notification OR timer due
        wake_at = self._state.auto_wake_at
        now = self._clock.now()

        if wake_at is not None and wake_at <= now:
            return "timer_due"

        # Race: inbox event vs timer sleep
        if wake_at is not None:
            timer_task = asyncio.ensure_future(self._clock.sleep_until(wake_at))
            event_task = asyncio.ensure_future(self._wait_event())

            done, pending = await asyncio.wait(
                {timer_task, event_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if timer_task in done:
                return "timer_due"
            return "inbox_message"
        else:
            # No timer — pure inbox wait
            await self._wait_event()
            return "inbox_message"

    async def _wait_event(self) -> None:
        """Wait on the wake event."""
        await self._wake_event.wait()

    async def _run_turn(self, msg: InboxMessage) -> None:
        """Execute exactly one model turn for the given message."""
        self._state.status = RunnerStatus.ACTIVE
        self._state.last_active_at = self._clock.now()

        try:
            session_id = self._state.session_id or f"{self._agent_id}-session"
            self._state.session_id = session_id
            result = self._invoke_fn(session_id, msg.content)
            if inspect.isawaitable(result):
                await result
            self._state.turn_count += 1
        except Exception as exc:
            logger.exception("agent %s turn failed: %s", self._agent_id, exc)
            self._state.status = RunnerStatus.ERROR

    async def _persist(self) -> None:
        """Save runner state to the persistence port."""
        await self._persistence.save_state(self._state)
