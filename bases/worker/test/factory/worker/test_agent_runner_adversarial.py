"""Adversarial behavior tests for AgentRunner — break the loop.

Attack angles: exception recovery, stop-mid-turn, spurious wake,
timer+message race, multi-drain, restart-from-error, starvation-class
bugs, and persistence aliasing.

All tests use real in-memory fakes at the port boundaries;
only invoke_fn is mocked. Arrange/act/assert structure, behavior-doc names.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from factory.worker.runtime.agent_runner import AgentRunner
from factory.worker.runtime.agent_runner_models import (
    AgentRunnerState,
    InboxMessage,
    RunnerStatus,
)
from factory.worker.runtime.adapters.in_memory_runner import (
    FakeClock,
    InMemoryInbox,
    InMemoryPersistence,
)


@pytest.fixture
def inbox():
    return InMemoryInbox()


@pytest.fixture
def clock():
    return FakeClock(start=datetime(2026, 6, 30, 12, 0, 0))


@pytest.fixture
def persistence():
    return InMemoryPersistence()


@pytest.fixture
def invoke_fn():
    return MagicMock()


def _make_runner(agent_id, inbox, clock, persistence, invoke_fn, **kwargs):
    return AgentRunner(
        agent_id=agent_id,
        inbox=inbox,
        clock=clock,
        persistence=persistence,
        invoke_fn=invoke_fn,
        **kwargs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 1: invoke_fn raises → runner sets ERROR, persists, keeps looping
# ─────────────────────────────────────────────────────────────────────────────


class TestInvokeFnRaisesRecovery:
    """WHEN invoke_fn raises THEN runner transitions to ERROR, persists,
    and can process the NEXT message without wedging."""

    async def test_exception_sets_error_status_and_persists(
        self, inbox, clock, persistence, invoke_fn
    ):
        invoke_fn.side_effect = RuntimeError("model exploded")
        runner = _make_runner("err-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        await inbox.enqueue(InboxMessage(agent_id="err-agent", content="boom"))
        runner.wake()
        await asyncio.sleep(0.1)

        # invoke was called
        assert invoke_fn.call_count == 1

        # State persisted (turn failed, so turn_count stays 0)
        saved = await persistence.load_state("err-agent")
        assert saved is not None
        # BUG PROBE: _park() unconditionally sets PARKED, clobbering ERROR status.
        # If persisted BEFORE park, saved.status should be ERROR.
        # If persisted AFTER park, saved.status will be PARKED.
        # The code does: _run_turn (ERROR) → _persist() → _park() (PARKED)
        # So the saved state reflects ERROR BEFORE _park overwrites.
        # Actually: _persist saves current self._state; _park then mutates it.
        # So the saved status IS the status at persist-time = ERROR.
        assert saved.status == RunnerStatus.ERROR

        runner.stop()
        await task

    async def test_runner_recovers_and_processes_next_message_after_error(
        self, inbox, clock, persistence, invoke_fn
    ):
        # First call explodes, second succeeds
        invoke_fn.side_effect = [RuntimeError("crash"), None]
        runner = _make_runner("recover-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # First message → error
        await inbox.enqueue(InboxMessage(agent_id="recover-agent", content="bad"))
        runner.wake()
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 1
        assert runner.is_parked  # re-parked after error turn

        # Second message → should work fine
        await inbox.enqueue(InboxMessage(agent_id="recover-agent", content="good"))
        runner.wake()
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 2
        invoke_fn.assert_called_with("recover-agent-session", "good")
        assert runner.state.turn_count == 1  # only the success counted

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 2: stop() called mid-turn and while parked
# ─────────────────────────────────────────────────────────────────────────────


class TestStopMidTurn:
    """WHEN stop() is called while invoke_fn is running
    THEN the current turn completes, state is persisted, loop exits cleanly."""

    async def test_stop_during_invoke_exits_after_turn(
        self, inbox, clock, persistence, invoke_fn
    ):
        stop_called = asyncio.Event()

        def slow_invoke(session_id, content):
            # Simulate a blocking invoke; stop is called while we're here
            stop_called.set()
            # Spin-wait briefly to simulate work
            import time
            time.sleep(0.05)

        invoke_fn.side_effect = slow_invoke
        runner = _make_runner("stop-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        await inbox.enqueue(InboxMessage(agent_id="stop-agent", content="working"))
        runner.wake()

        # Wait until invoke_fn is running
        await asyncio.wait_for(stop_called.wait(), timeout=2.0)
        runner.stop()

        # The task should exit cleanly (not hang)
        await asyncio.wait_for(task, timeout=3.0)

        # Turn completed (state persisted)
        assert invoke_fn.call_count == 1
        saved = await persistence.load_state("stop-agent")
        assert saved is not None
        assert saved.turn_count == 1

    async def test_stop_while_parked_exits_immediately(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("park-stop", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        assert runner.is_parked
        runner.stop()

        # Should exit very quickly
        await asyncio.wait_for(task, timeout=2.0)
        assert invoke_fn.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 3: Spurious wake with empty inbox → re-park, no spin
# ─────────────────────────────────────────────────────────────────────────────


class TestSpuriousWakeEmptyInbox:
    """WHEN wake() fires but inbox is empty THEN runner re-parks
    without invoking or spinning."""

    async def test_spurious_wake_reparks_without_invoke(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("spurious-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Spurious wake — nothing in inbox
        runner.wake()
        await asyncio.sleep(0.1)

        # No invoke, still parked
        assert invoke_fn.call_count == 0
        assert runner.is_parked

        # Now send real work — should still function
        await inbox.enqueue(InboxMessage(agent_id="spurious-agent", content="real"))
        runner.wake()
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 1
        runner.stop()
        await task

    async def test_multiple_spurious_wakes_no_spin(
        self, inbox, clock, persistence, invoke_fn
    ):
        """Rapid fire 10 spurious wakes — must not spin/starve."""
        runner = _make_runner("spammer", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        for _ in range(10):
            runner.wake()
        await asyncio.sleep(0.2)

        assert invoke_fn.call_count == 0
        assert runner.is_parked

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 4: Timer fires + inbox message arrive simultaneously
# ─────────────────────────────────────────────────────────────────────────────


class TestTimerAndMessageRace:
    """WHEN timer_due AND inbox message both present
    THEN exactly one turn fires, auto_wake_at is cleared."""

    async def test_timer_and_message_exactly_one_drain(
        self, inbox, clock, persistence, invoke_fn
    ):
        wake_time = clock.now() + timedelta(minutes=1)
        runner = _make_runner(
            "race-agent", inbox, clock, persistence, invoke_fn,
            auto_wake_at=wake_time,
        )
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Both conditions: enqueue message AND advance clock past timer
        await inbox.enqueue(InboxMessage(agent_id="race-agent", content="raced"))
        clock.advance(timedelta(minutes=2))
        runner.wake()  # Also signal inbox
        await asyncio.sleep(0.15)

        # Exactly one turn
        assert invoke_fn.call_count == 1
        # Timer cleared
        assert runner.state.auto_wake_at is None

        runner.stop()
        await task

    async def test_timer_fires_with_empty_inbox_reparks_clears_timer(
        self, inbox, clock, persistence, invoke_fn
    ):
        """Timer fires, inbox is empty — re-park, timer cleared, no invoke."""
        wake_time = clock.now() + timedelta(minutes=1)
        runner = _make_runner(
            "timer-empty", inbox, clock, persistence, invoke_fn,
            auto_wake_at=wake_time,
        )
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Advance clock past timer (no inbox message)
        clock.advance(timedelta(minutes=2))
        # The loop won't naturally re-check unless we trigger it —
        # in the current impl, the timer race is checked at loop top.
        # For the "already past" check to trigger, the loop must cycle.
        # The parked state means it's blocking on _wait_for_wake.
        # sleep_until returns immediately if target <= now, so the timer_task wins.
        await asyncio.sleep(0.15)

        assert invoke_fn.call_count == 0
        assert runner.is_parked
        assert runner.state.auto_wake_at is None

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 5: Two messages + single wake → only one drains
# ─────────────────────────────────────────────────────────────────────────────


class TestTwoMessagesSingleWake:
    """WHEN two messages are enqueued and a single wake fires
    THEN exactly one message drains (second requires another wake)."""

    async def test_second_message_requires_second_wake(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("drain-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        await inbox.enqueue(InboxMessage(agent_id="drain-agent", content="msg-1"))
        await inbox.enqueue(InboxMessage(agent_id="drain-agent", content="msg-2"))
        runner.wake()
        await asyncio.sleep(0.1)

        # Only first processed
        assert invoke_fn.call_count == 1
        invoke_fn.assert_called_with("drain-agent-session", "msg-1")

        # Second is still pending — verify inbox is NOT empty
        assert not await inbox.is_empty("drain-agent")

        # Second wake drains second message
        runner.wake()
        await asyncio.sleep(0.1)
        assert invoke_fn.call_count == 2
        invoke_fn.assert_called_with("drain-agent-session", "msg-2")

        # Now inbox is empty
        assert await inbox.is_empty("drain-agent")

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 6: Restart from ACTIVE or ERROR status → restore + resume
# ─────────────────────────────────────────────────────────────────────────────


class TestRestartFromActiveOrError:
    """WHEN runner restores state that was ACTIVE/ERROR at crash time
    THEN it starts cleanly from PARKED."""

    async def test_restore_from_error_status_resumes_to_parked(
        self, inbox, clock, persistence, invoke_fn
    ):
        # Simulate prior crash: manually persist ERROR state
        crash_state = AgentRunnerState(
            agent_id="crash-agent",
            status=RunnerStatus.ERROR,
            turn_count=3,
            session_id="crash-agent-session",
            last_active_at=datetime(2026, 6, 30, 11, 0, 0),
        )
        await persistence.save_state(crash_state)

        # New runner restores
        runner = _make_runner("crash-agent", inbox, clock, persistence, invoke_fn)
        await runner.restore()

        assert runner.state.status == RunnerStatus.ERROR
        assert runner.state.turn_count == 3

        # Start the loop — it should park and be functional
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        assert runner.is_parked

        # Can process messages
        await inbox.enqueue(InboxMessage(agent_id="crash-agent", content="post-crash"))
        runner.wake()
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 1
        assert runner.state.turn_count == 4

        runner.stop()
        await task

    async def test_restore_from_active_status_resumes_to_parked(
        self, inbox, clock, persistence, invoke_fn
    ):
        # Simulate crash while ACTIVE
        active_state = AgentRunnerState(
            agent_id="active-crash",
            status=RunnerStatus.ACTIVE,
            turn_count=7,
            session_id="active-crash-session",
        )
        await persistence.save_state(active_state)

        runner = _make_runner("active-crash", inbox, clock, persistence, invoke_fn)
        await runner.restore()

        assert runner.state.status == RunnerStatus.ACTIVE

        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Parked after start, state preserved
        assert runner.is_parked
        assert runner.state.turn_count == 7

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 7: Starvation — await suspension points
# ─────────────────────────────────────────────────────────────────────────────


class TestNoStarvationOnTimerRefire:
    """The fixed bug: a one-shot auto_wake_at not being cleared caused
    event-loop starvation. Verify the timer is cleared after first fire
    and the loop doesn't spin."""

    async def test_timer_cleared_after_fire_no_refire(
        self, inbox, clock, persistence, invoke_fn
    ):
        wake_time = clock.now() + timedelta(seconds=30)
        runner = _make_runner(
            "starve-agent", inbox, clock, persistence, invoke_fn,
            auto_wake_at=wake_time,
        )
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Enqueue message and advance clock to trigger timer
        await inbox.enqueue(InboxMessage(agent_id="starve-agent", content="timer-work"))
        clock.advance(timedelta(seconds=31))
        await asyncio.sleep(0.15)

        # Timer cleared
        assert runner.state.auto_wake_at is None
        assert invoke_fn.call_count == 1

        # Advance clock further — should NOT trigger another wake
        clock.advance(timedelta(minutes=10))
        await asyncio.sleep(0.1)

        # Still just 1 invocation — no re-fire
        assert invoke_fn.call_count == 1
        assert runner.is_parked

        runner.stop()
        await task

    async def test_event_loop_yields_control_during_park(
        self, inbox, clock, persistence, invoke_fn
    ):
        """Verify the event loop isn't starved by the runner.
        If starvation occurs, this concurrent task won't run."""
        runner = _make_runner("yield-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())

        # A competing task should be able to run
        canary = asyncio.Event()

        async def concurrent_work():
            await asyncio.sleep(0.01)
            canary.set()

        asyncio.create_task(concurrent_work())
        await asyncio.sleep(0.1)

        # If the runner starves the loop, canary never fires
        assert canary.is_set(), "event loop was starved by the runner!"

        runner.stop()
        await task


# ─────────────────────────────────────────────────────────────────────────────
# ATTACK 8: Persistence aliasing — saved state not mutable by live runner
# ─────────────────────────────────────────────────────────────────────────────


class TestPersistenceAliasing:
    """WHEN state is saved THEN mutations to the live runner state
    do NOT corrupt the persisted snapshot."""

    async def test_saved_state_immune_to_live_mutation(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("alias-agent", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Trigger a turn to persist state
        await inbox.enqueue(InboxMessage(agent_id="alias-agent", content="persist-me"))
        runner.wake()
        await asyncio.sleep(0.1)

        # Snapshot at this point
        saved_before = await persistence.load_state("alias-agent")
        turn_count_at_save = saved_before.turn_count

        # Now do more work (mutates live state)
        await inbox.enqueue(InboxMessage(agent_id="alias-agent", content="second"))
        runner.wake()
        await asyncio.sleep(0.1)

        # Reload the EARLIER save — must not have been mutated
        # (This tests InMemoryPersistence's copy semantics)
        saved_after_reload = await persistence.load_state("alias-agent")
        # After second turn, it should have turn_count=2 (the save happens
        # after each turn). But the PREVIOUSLY loaded saved_before should
        # still reflect turn_count=1
        assert saved_before.turn_count == turn_count_at_save
        assert saved_after_reload.turn_count == turn_count_at_save + 1

        runner.stop()
        await task

    async def test_load_returns_independent_copy(
        self, inbox, clock, persistence, invoke_fn
    ):
        """Two loads return independent objects — mutating one doesn't affect the other."""
        state = AgentRunnerState(agent_id="copy-test", turn_count=5)
        await persistence.save_state(state)

        load1 = await persistence.load_state("copy-test")
        load2 = await persistence.load_state("copy-test")

        load1.turn_count = 99
        assert load2.turn_count == 5  # Must be independent
