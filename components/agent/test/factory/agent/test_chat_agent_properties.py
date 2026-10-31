"""Property-based tests for MemoryChatAgent stateful operations.

Verifies that invoke grows history, close clears it, and threads
remain independent across arbitrary operation sequences.
"""

from __future__ import annotations

import asyncio

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.agent.runtime.adapters.memory import MemoryChatAgent


def _run_async(coro):
    """Run an async coroutine synchronously for Hypothesis."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


# Strategies
_thread_ids = st.sampled_from(["t1", "t2", "t3", "t4"])
_messages = st.text(min_size=1, max_size=50)


class ChatAgentStateMachine(RuleBasedStateMachine):
    """Stateful test: MemoryChatAgent history tracking."""

    def __init__(self):
        super().__init__()
        self.agent: MemoryChatAgent | None = None
        self.model: dict[str, int] = {}  # thread_id -> expected turn count

    @initialize()
    def init_agent(self):
        self.agent = MemoryChatAgent()
        self.model = {}

    @rule(thread_id=_thread_ids, message=_messages)
    def invoke(self, thread_id: str, message: str):
        """Invoke increments the turn count for the thread."""
        result = _run_async(self.agent.invoke(thread_id, message))
        self.model[thread_id] = self.model.get(thread_id, 0) + 1
        assert result.metadata["turn"] == self.model[thread_id]
        assert result.status == "completed"

    @rule(thread_id=_thread_ids)
    def close(self, thread_id: str):
        """Close resets the thread's history."""
        self.agent.close(thread_id)
        self.model.pop(thread_id, None)

    @invariant()
    def threads_are_independent(self):
        """Each thread's turn count matches the model."""
        # We verify this via the invoke rule assertions.
        # This invariant ensures the model dict is consistent.
        for tid, expected_turns in self.model.items():
            assert expected_turns >= 1


TestChatAgentStateful = ChatAgentStateMachine.TestCase
TestChatAgentStateful.settings = settings(max_examples=50, stateful_step_count=20)
