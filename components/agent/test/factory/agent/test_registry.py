"""Tests for registry modules - Agent and Swarm registries.

See also:
- test_registry_graphs.py - Graph registry tests
- test_registry_tools.py - Tool registry tests
"""

import pytest
from pathlib import Path
import tempfile

from factory.agent.registry.agents import AgentRegistry
from factory.agent.registry.swarms import SwarmRegistry


@pytest.fixture
def temp_agents_dir():
    """Create a temporary agents directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)

        # Create sample agent configs
        (agents_dir / "researcher.yaml").write_text("""
id: researcher
name: Research Agent
model: test-model
system_prompt: You are a researcher.
tools:
  - strands_tools.http_request
""")

        (agents_dir / "analyst.yaml").write_text("""
id: analyst
name: Analysis Agent
model: test-model
system_prompt: You are an analyst.
""")

        yield agents_dir


@pytest.fixture
def temp_swarms_dir():
    """Create a temporary swarms directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        swarms_dir = Path(tmpdir)

        (swarms_dir / "research_swarm.yaml").write_text("""
id: research_swarm
name: Research Swarm
entry_point: researcher
max_handoffs: 10
agents:
  - id: researcher
    name: Researcher
    model: test-model
    system_prompt: Research things.
  - id: analyst
    name: Analyst
    model: test-model
    system_prompt: Analyze things.
""")

        yield swarms_dir


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    @pytest.mark.asyncio
    async def test_load_agents(self, temp_agents_dir):
        """Test loading agents from directory.

        bd:python-factory-d4roe.1 — ``load()`` now seeds built-in
        personas (``AGENTS_TYPED``) FIRST, then overlays disk personas.
        Disk agents are still present; the count includes built-ins.
        """
        from factory.agent.registry.defaults import get_default_agents
        registry = AgentRegistry(temp_agents_dir)
        await registry.load()

        builtins = len(get_default_agents())
        assert len(registry.agents) == builtins + 2
        assert "researcher" in registry.agents
        assert "analyst" in registry.agents
        # A built-in persona is seeded even when only disk agents exist.
        assert "companion-x-default" in registry.agents

    @pytest.mark.asyncio
    async def test_get_agent(self, temp_agents_dir):
        """Test getting agent by ID."""
        registry = AgentRegistry(temp_agents_dir)
        await registry.load()

        agent = registry.get("researcher")
        assert agent is not None
        assert agent.name == "Research Agent"

        missing = registry.get("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_list_agents(self, temp_agents_dir):
        """Test listing all agents.

        bd:python-factory-d4roe.1 — built-ins are seeded alongside disk
        personas. Both disk agents still surface in the listing.
        """
        from factory.agent.registry.defaults import get_default_agents
        registry = AgentRegistry(temp_agents_dir)
        await registry.load()

        agents = registry.list_agents()
        assert len(agents) == len(get_default_agents()) + 2

        names = [a["name"] for a in agents]
        assert "Research Agent" in names
        assert "Analysis Agent" in names


class TestSwarmRegistry:
    """Tests for SwarmRegistry."""

    @pytest.mark.asyncio
    async def test_load_swarms(self, temp_swarms_dir):
        """Test loading swarms from directory."""
        registry = SwarmRegistry(temp_swarms_dir)
        await registry.load()

        assert len(registry.swarms) == 1
        assert "research_swarm" in registry.swarms

    @pytest.mark.asyncio
    async def test_get_swarm(self, temp_swarms_dir):
        """Test getting swarm by ID."""
        registry = SwarmRegistry(temp_swarms_dir)
        await registry.load()

        swarm = registry.get("research_swarm")
        assert swarm is not None
        assert swarm.name == "Research Swarm"
        assert swarm.entry_point == "researcher"
        assert len(swarm.agents) == 2

    @pytest.mark.asyncio
    async def test_list_swarms(self, temp_swarms_dir):
        """Test listing all swarms."""
        registry = SwarmRegistry(temp_swarms_dir)
        await registry.load()

        swarms = registry.list_swarms()
        assert len(swarms) == 1
        assert swarms[0]["id"] == "research_swarm"
        assert swarms[0]["agent_count"] == 2
