"""Behavior tests for AgentRunner — the supervised long-lived loop.

Tests assert observable outcomes, not internals. Mock ONLY at
the invoke_fn boundary (the model call). Inbox, clock, and
persistence are in-memory fakes (real objects, not mocks).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from factory.worker.runtime.agent_runner import AgentRunner
from factory.worker.runtime.agent_runner_models import InboxMessage, RunnerStatus
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


class TestParksWhenInboxEmpty:
    """R1.5: WHEN no pending input THEN parks (zero tokens)."""

    async def test_parks_immediately_on_start_with_empty_inbox(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("agent-a", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())

        # Give the loop time to park
        await asyncio.sleep(0.05)

        assert runner.is_parked
        assert invoke_fn.call_count == 0

        runner.stop()
        await task


class TestWakesOnEnqueuedMessage:
    """R1.6: WHEN a message arrives THEN wakes."""

    async def test_wakes_and_invokes_on_message(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("agent-b", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Enqueue a message and wake
        msg = InboxMessage(agent_id="agent-b", content="hello")
        await inbox.enqueue(msg)
        runner.wake()

        # Let the turn run
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 1
        invoke_fn.assert_called_once_with("agent-b-session", "hello")

        # Should be parked again after the turn
        assert runner.is_parked

        runner.stop()
        await task


class TestWakesWhenTimerDue:
    """R1.6: WHEN auto_wake_at passes THEN wakes."""

    async def test_wakes_on_timer(
        self, inbox, clock, persistence, invoke_fn
    ):
        wake_time = clock.now() + timedelta(minutes=5)
        runner = _make_runner(
            "agent-c", inbox, clock, persistence, invoke_fn,
            auto_wake_at=wake_time,
        )
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Still parked (timer not due)
        assert runner.is_parked
        assert invoke_fn.call_count == 0

        # Enqueue something so the drain has work when timer fires
        msg = InboxMessage(agent_id="agent-c", content="scheduled-work")
        await inbox.enqueue(msg)

        # Advance clock past wake time
        clock.advance(timedelta(minutes=6))
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 1
        invoke_fn.assert_called_once_with("agent-c-session", "scheduled-work")

        runner.stop()
        await task


class TestRunsExactlyOneTurnPerDrain:
    """R1 loop: drain inbox → ONE invoke → persist → park."""

    async def test_multiple_messages_processed_one_per_wake(
        self, inbox, clock, persistence, invoke_fn
    ):
        runner = _make_runner("agent-d", inbox, clock, persistence, invoke_fn)
        task = asyncio.create_task(runner.start())
        await asyncio.sleep(0.05)

        # Enqueue two messages
        await inbox.enqueue(InboxMessage(agent_id="agent-d", content="first"))
        await inbox.enqueue(InboxMessage(agent_id="agent-d", content="second"))
        runner.wake()
        await asyncio.sleep(0.1)

        # Only ONE turn processed per wake cycle
        assert invoke_fn.call_count == 1
        invoke_fn.assert_called_with("agent-d-session", "first")

        # Wake again — second message drains
        runner.wake()
        await asyncio.sleep(0.1)

        assert invoke_fn.call_count == 2
        invoke_fn.assert_called_with("agent-d-session", "second")

        runner.stop()
        await task


class TestPersistsAndResumesAcrossSimulatedRestart:
    """R1.2: WHEN host restarts THEN state restored from durable storage."""

    async def test_restore_resumes_turn_count(
        self, inbox, clock, persistence, invoke_fn
    ):
        # Phase 1: run one turn then stop
        runner1 = _make_runner("agent-e", inbox, clock, persistence, invoke_fn)
        task1 = asyncio.create_task(runner1.start())
        await asyncio.sleep(0.05)

        await inbox.enqueue(InboxMessage(agent_id="agent-e", content="turn-1"))
        runner1.wake()
        await asyncio.sleep(0.1)

        assert runner1.state.turn_count == 1
        runner1.stop()
        await task1

        # Phase 2: simulate restart — new runner, same persistence
        invoke_fn2 = MagicMock()
        runner2 = _make_runner("agent-e", inbox, clock, persistence, invoke_fn2)
        await runner2.restore()

        # State survived
        assert runner2.state.turn_count == 1
        assert runner2.state.session_id == "agent-e-session"

        # Can continue running
        task2 = asyncio.create_task(runner2.start())
        await asyncio.sleep(0.05)

        await inbox.enqueue(InboxMessage(agent_id="agent-e", content="turn-2"))
        runner2.wake()
        await asyncio.sleep(0.1)

        assert runner2.state.turn_count == 2
        invoke_fn2.assert_called_once_with("agent-e-session", "turn-2")

        runner2.stop()
        await task2
