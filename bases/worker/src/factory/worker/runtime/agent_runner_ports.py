"""Agent runner ports — Protocol interfaces for the supervised runner.

Three injected boundaries:
- InboxPort: message queue (durable in prod, in-memory for tests)
- ClockPort: time source (fakeable for deterministic tests)
- RunnerPersistencePort: save/load runner state across restarts
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .agent_runner_models import AgentRunnerState, InboxMessage


@runtime_checkable
class InboxPort(Protocol):
    """Port: per-agent durable message inbox."""

    async def enqueue(self, message: InboxMessage) -> None:
        """Put a message on the agent's inbox."""
        ...

    async def dequeue(self, agent_id: str) -> InboxMessage | None:
        """Non-blocking pop of the next message. Returns None if empty."""
        ...

    async def is_empty(self, agent_id: str) -> bool:
        """True if no messages pending for this agent."""
        ...

    async def wait_for_message(self, agent_id: str) -> InboxMessage:
        """Block until a message arrives. Used by the park loop."""
        ...


@runtime_checkable
class ClockPort(Protocol):
    """Port: time source for wake scheduling."""

    def now(self) -> datetime:
        """Current time."""
        ...

    async def sleep_until(self, target: datetime) -> None:
        """Sleep until target time (or return immediately if past)."""
        ...


@runtime_checkable
class RunnerPersistencePort(Protocol):
    """Port: save/load agent runner state across restarts."""

    async def save_state(self, state: AgentRunnerState) -> None:
        """Persist runner state."""
        ...

    async def load_state(self, agent_id: str) -> AgentRunnerState | None:
        """Load persisted state. Returns None if no prior state."""
        ...

    async def list_agents(self) -> list[str]:
        """List all agent_ids with persisted state."""
        ...
