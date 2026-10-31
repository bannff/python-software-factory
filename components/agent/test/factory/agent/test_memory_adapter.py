"""Tests for memory adapter implementations.

These tests verify the mock/in-memory adapters work correctly for testing
without requiring LLM dependencies.
"""

from __future__ import annotations

import pytest

from factory.agent.runtime.ports import AgentConfig
from factory.agent.runtime.adapters import (
    MemoryAgentRuntime,
    MemorySwarmRuntime,
    MemoryGraphRuntime,
    MemoryToolLoader,
)


class TestMemoryAgentRuntime:
    """Tests for MemoryAgentRuntime."""

    def test_create_agent(self) -> None:
        """Test creating a mock agent."""
        runtime = MemoryAgentRuntime()
        config = AgentConfig(
            name="test-agent",
            system_prompt="You are a test agent",
            model="test-model",
        )
        agent = runtime.create_agent(config)

        assert agent.name == "test-agent"
        assert agent.system_prompt == "You are a test agent"
        assert agent.model == "test-model"

    @pytest.mark.asyncio
    async def test_invoke_async_default_response(self) -> None:
        """Test invoking agent returns default response."""
        runtime = MemoryAgentRuntime()
        config = AgentConfig(name="test-agent")
        agent = runtime.create_agent(config)

        result = await runtime.invoke_async(agent, "Hello")

        assert result.status == "completed"
        assert "Mock response" in result.output
        assert result.metadata["agent"] == "test-agent"
        assert result.metadata["call_count"] == 1

    @pytest.mark.asyncio
    async def test_invoke_async_canned_responses(self) -> None:
        """Test invoking agent with canned responses."""
        runtime = MemoryAgentRuntime()
        runtime.set_response("test-agent", ["Response 1", "Response 2"])
        config = AgentConfig(name="test-agent")
        agent = runtime.create_agent(config)

        result1 = await runtime.invoke_async(agent, "First call")
        result2 = await runtime.invoke_async(agent, "Second call")
        result3 = await runtime.invoke_async(agent, "Third call")

        assert result1.output == "Response 1"
        assert result2.output == "Response 2"
        assert result3.output == "Response 1"  # Cycles back

    @pytest.mark.asyncio
    async def test_stream_async(self) -> None:
        """Test streaming responses."""
        runtime = MemoryAgentRuntime()
        runtime.set_response("test-agent", ["Hello world"])
        config = AgentConfig(name="test-agent")
        agent = runtime.create_agent(config)

        chunks = []
        async for chunk in runtime.stream_async(agent, "Test"):
            chunks.append(chunk)

        assert len(chunks) == 2  # "Hello " and "world "
        assert "".join(chunks).strip() == "Hello world"

    def test_get_call_count(self) -> None:
        """Test tracking call counts."""
        runtime = MemoryAgentRuntime()
        config = AgentConfig(name="test-agent")
        runtime.create_agent(config)

        assert runtime.get_call_count("test-agent") == 0
        assert runtime.get_call_count("nonexistent") == 0


class TestMemorySwarmRuntime:
    """Tests for MemorySwarmRuntime."""

    def test_create_swarm(self) -> None:
        """Test creating a mock swarm."""
        runtime = MemorySwarmRuntime()
        agents = [{"name": "agent1"}, {"name": "agent2"}]
        swarm = runtime.create_swarm(agents, entry_point=agents[0])

        assert "id" in swarm
        assert swarm["agents"] == agents
        assert swarm["entry_point"] == agents[0]

    @pytest.mark.asyncio
    async def test_invoke_async(self) -> None:
        """Test executing a mock swarm."""
        runtime = MemorySwarmRuntime()
        agents = [{"name": "agent1"}, {"name": "agent2"}]
        swarm = runtime.create_swarm(agents, entry_point=agents[0])

        result = await runtime.invoke_async(swarm, "Test task")

        assert result.status == "completed"
        assert "Test task" in result.output
        assert result.execution_time > 0


class TestMemoryGraphRuntime:
    """Tests for MemoryGraphRuntime."""

    def test_build_graph(self) -> None:
        """Test building a mock graph."""
        runtime = MemoryGraphRuntime()
        builder = runtime.create_builder()

        runtime.add_node(builder, {"type": "start"}, "start")
        runtime.add_node(builder, {"type": "end"}, "end")
        runtime.add_edge(builder, "start", "end")
        runtime.set_entry_point(builder, "start")

        graph = runtime.build(builder)

        assert "start" in graph["nodes"]
        assert "end" in graph["nodes"]
        assert graph["entry_point"] == "start"

    @pytest.mark.asyncio
    async def test_invoke_async(self) -> None:
        """Test executing a mock graph."""
        runtime = MemoryGraphRuntime()
        builder = runtime.create_builder()
        runtime.add_node(builder, {}, "node1")
        runtime.add_node(builder, {}, "node2")
        runtime.set_entry_point(builder, "node1")
        graph = runtime.build(builder)

        result = await runtime.invoke_async(graph, "Test task")

        assert result.status == "completed"
        assert "node1" in result.execution_order
        assert "node2" in result.execution_order


class TestMemoryToolLoader:
    """Tests for MemoryToolLoader."""

    def test_register_and_load_tools(self) -> None:
        """Test registering and loading mock tools."""
        loader = MemoryToolLoader()

        def mock_tool() -> str:
            return "mock"

        loader.register_tool("mock_tool", mock_tool)

        tools = loader.load_builtin_tools()
        assert len(tools) == 1
        assert tools[0] == mock_tool

    def test_load_specific_tool(self) -> None:
        """Test loading a specific tool by name."""
        loader = MemoryToolLoader()
        loader.register_tool("my_tool", lambda: "test")

        tool = loader.load_tool("my_tool")
        assert tool is not None
        assert tool() == "test"

        missing = loader.load_tool("nonexistent")
        assert missing is None
