"""Integration tests for MCP server tools."""

import pytest
from pathlib import Path
import tempfile

from factory.agent import SuperAgent
from factory.agent.server import WorkflowState


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory with sample configs."""
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

        # Create a sample swarm
        (config_dir / "swarms" / "test_swarm.yaml").write_text("""
id: test_swarm
name: Test Swarm
entry_point: agent1
agents:
  - id: agent1
    name: Agent 1
    model: test-model
    system_prompt: Test agent 1.
""")

        # Create a sample graph
        (config_dir / "graphs" / "test_graph.yaml").write_text("""
id: test_graph
name: Test Graph
nodes:
  - id: node1
    type: agent
    agent_id: test_agent
edges: []
entry_points:
  - node1
""")

        yield config_dir


class TestWorkflowTracking:
    """Tests for workflow state tracking."""

    @pytest.mark.asyncio
    async def test_workflow_status_not_found(self, temp_config_dir):
        """Test get_workflow_status with non-existent workflow."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()

        # Directly test the workflow lookup
        result = agent.workflows.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_workflow_tracking(self, temp_config_dir):
        """Test workflow state tracking."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()

        # Add a workflow
        workflow_id = "test123"
        agent.workflows[workflow_id] = WorkflowState(status="running")

        # Check it's tracked
        assert workflow_id in agent.workflows
        assert agent.workflows[workflow_id].status == "running"

        # Update status
        agent.workflows[workflow_id].status = "completed"
        agent.workflows[workflow_id].result = {"output": "done"}

        assert agent.workflows[workflow_id].status == "completed"
        assert agent.workflows[workflow_id].result == {"output": "done"}


class TestMCPToolIntegration:
    """Integration tests for MCP tools."""

    @pytest.mark.asyncio
    async def test_swarm_registry_returns_schemas(self, temp_config_dir):
        """Test that swarm registry returns schemas."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()

        swarms = agent.swarm_registry.list_swarms_with_schemas()

        assert len(swarms) == 1
        assert swarms[0]["id"] == "test_swarm"
        assert "agents" in swarms[0]

    @pytest.mark.asyncio
    async def test_graph_registry_returns_structure(self, temp_config_dir):
        """Test that graph registry returns structure."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()

        graphs = agent.graph_registry.list_graphs_with_schemas()

        assert len(graphs) == 1
        assert graphs[0]["id"] == "test_graph"
        assert "nodes" in graphs[0]
        assert "edges" in graphs[0]
