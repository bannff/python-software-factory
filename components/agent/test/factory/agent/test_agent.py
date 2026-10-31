"""Tests for SuperAgent class."""

import pytest
from pathlib import Path
import tempfile

from factory.agent import SuperAgent


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create subdirectories
        (config_dir / "agents").mkdir()
        (config_dir / "swarms").mkdir()
        (config_dir / "graphs").mkdir()
        (config_dir / "tools").mkdir()

        # Create settings.yaml
        (config_dir / "settings.yaml").write_text("""
defaults:
  model: test-model
  timeout: 60
""")

        # Create a sample agent
        (config_dir / "agents" / "test_agent.yaml").write_text("""
id: test_agent
name: Test Agent
model: test-model
system_prompt: You are a test agent.
tools: []
""")

        yield config_dir


@pytest.mark.asyncio
async def test_super_agent_init(temp_config_dir):
    """Test SuperAgent initialization."""
    agent = SuperAgent(config_dir=str(temp_config_dir))
    assert agent.config_dir == temp_config_dir
    assert not agent._initialized


@pytest.mark.asyncio
async def test_super_agent_initialize(temp_config_dir):
    """Test SuperAgent.initialize() loads registries."""
    agent = SuperAgent(config_dir=str(temp_config_dir))
    await agent.initialize()

    assert agent._initialized
    assert agent.agent_registry is not None
    assert agent.swarm_registry is not None
    assert agent.graph_registry is not None
    assert agent.tool_registry is not None
    assert agent.mcp is not None


@pytest.mark.asyncio
async def test_super_agent_loads_agents(temp_config_dir):
    """Test that agents are loaded from config."""
    agent = SuperAgent(config_dir=str(temp_config_dir))
    await agent.initialize()

    assert "test_agent" in agent.agent_registry.agents
    config = agent.agent_registry.get("test_agent")
    assert config.name == "Test Agent"


@pytest.mark.asyncio
async def test_super_agent_get_capabilities(temp_config_dir):
    """Test get_capabilities returns correct structure."""
    agent = SuperAgent(config_dir=str(temp_config_dir))
    await agent.initialize()

    caps = agent.get_capabilities()

    assert "deterministic_tools" in caps
    assert "swarms" in caps
    assert "graphs" in caps
    assert "agents" in caps


@pytest.mark.asyncio
async def test_super_agent_health_check(temp_config_dir):
    """Test health_check returns correct status."""
    agent = SuperAgent(config_dir=str(temp_config_dir))

    # Before initialization
    health = agent.health_check()
    assert health["status"] == "not_initialized"

    # After initialization
    await agent.initialize()
    health = agent.health_check()
    assert health["status"] == "healthy"
    # bd:python-factory-d4roe.1 — built-in personas are seeded alongside
    # the one disk agent (test_agent) loaded from temp_config_dir.
    from factory.agent.registry.defaults import get_default_agents
    assert health["agents_loaded"] == len(get_default_agents()) + 1


@pytest.mark.asyncio
async def test_super_agent_register_tool(temp_config_dir):
    """Test registering custom tools."""
    agent = SuperAgent(config_dir=str(temp_config_dir))

    def my_tool(arg: str) -> dict:
        return {"result": arg}

    agent.register_tool("my_tool", my_tool)
    await agent.initialize()

    assert "my_tool" in agent.tool_registry.tools


@pytest.mark.asyncio
async def test_super_agent_lifecycle_hooks(temp_config_dir):
    """Test lifecycle hooks are called."""
    agent = SuperAgent(config_dir=str(temp_config_dir))

    events = []

    def on_test_event(**kwargs):
        events.append(kwargs)

    agent.on("test_event", on_test_event)
    await agent.initialize()

    await agent._emit("test_event", foo="bar")

    assert len(events) == 1
    assert events[0]["foo"] == "bar"
