"""In-memory mock agent runtime for testing.

This adapter provides deterministic, canned responses without LLM calls.
Useful for unit tests and development without external dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from factory.agent.runtime.ports import AgentConfig, AgentResult, SwarmResult
from .memory_models import MockAgent
from .memory_chat import MemoryChatAgent as MemoryChatAgent  # noqa: F401 - re-export

logger = logging.getLogger(__name__)


class MemoryAgentRuntime:
    """In-memory implementation of AgentRuntime port.

    Stores agent definitions and returns deterministic responses for testing.
    No LLM calls - pure mock behavior.
    """

    def __init__(self) -> None:
        self._agents: dict[str, MockAgent] = {}
        self._default_response = "Mock response from memory adapter"
        self._canned_responses: dict[str, list[str]] = {}

    def set_response(self, agent_name: str, responses: list[str]) -> None:
        """Set canned responses for an agent (test helper)."""
        self._canned_responses[agent_name] = responses

    def set_default_response(self, response: str) -> None:
        """Set the default response for all agents."""
        self._default_response = response

    def create_agent(self, config: AgentConfig) -> MockAgent:
        """Create a mock agent from configuration."""
        agent = MockAgent(
            name=config.name,
            system_prompt=config.system_prompt,
            model=config.model or "mock-model",
            tools=config.tools,
        )
        self._agents[config.name] = agent
        return agent

    async def invoke_async(
        self, agent: MockAgent, message: str, **kwargs: Any
    ) -> AgentResult:
        """Invoke a mock agent - returns canned response."""
        agent.call_count += 1
        responses = self._canned_responses.get(agent.name, [])
        if responses:
            idx = (agent.call_count - 1) % len(responses)
            output = responses[idx]
        else:
            output = f"{self._default_response} for: {message[:50]}"

        return AgentResult(
            output=output,
            status="completed",
            metadata={"agent": agent.name, "call_count": agent.call_count},
        )

    async def stream_async(
        self, agent: MockAgent, message: str, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream mock responses - yields chunks of canned response."""
        result = await self.invoke_async(agent, message, **kwargs)
        words = result.output.split()
        for word in words:
            yield word + " "
            await asyncio.sleep(0.01)  # Simulate streaming delay

    def get_agent(self, name: str) -> MockAgent | None:
        """Get a registered agent by name (test helper)."""
        return self._agents.get(name)

    def get_call_count(self, name: str) -> int:
        """Get the call count for an agent (test helper)."""
        agent = self._agents.get(name)
        return agent.call_count if agent else 0


class MemorySwarmRuntime:
    """In-memory implementation of SwarmRuntime port."""

    def __init__(self) -> None:
        self._swarms: dict[str, Any] = {}
        self._default_output = "Mock swarm completed"
        self._execution_count = 0

    def set_default_output(self, output: str) -> None:
        """Set the default swarm output."""
        self._default_output = output

    def create_swarm(
        self,
        agents: list[Any],
        entry_point: Any,
        max_handoffs: int = 20,
        max_iterations: int = 20,
        hooks: list[Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Create a mock swarm. ``hooks`` accepted but ignored."""
        swarm_id = f"swarm_{len(self._swarms)}"
        swarm = {
            "id": swarm_id,
            "agents": agents,
            "entry_point": entry_point,
            "max_handoffs": max_handoffs,
            "max_iterations": max_iterations,
        }
        self._swarms[swarm_id] = swarm
        return swarm

    async def invoke_async(
        self, swarm: dict[str, Any], task: str, context: dict[str, Any] | None = None
    ) -> SwarmResult:
        """Execute a mock swarm - returns deterministic result."""
        self._execution_count += 1
        agent_names = [
            getattr(a, "name", f"agent_{i}") for i, a in enumerate(swarm.get("agents", []))
        ]
        return SwarmResult(
            status="completed",
            output=f"{self._default_output}: {task[:30]}",
            node_history=agent_names,
            execution_time=0.1,
        )



