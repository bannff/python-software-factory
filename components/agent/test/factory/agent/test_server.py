"""Tests for MCP server and tools - Core tests.

See also:
- test_server_integration.py - Integration tests for MCP tools
"""

import pytest
from pathlib import Path
import tempfile

from factory.agent import SuperAgent
from factory.agent.server import WorkflowState, generate_workflow_id


class TestWorkflowState:
    """Tests for WorkflowState class."""

    def test_initial_state(self):
        """Test initial workflow state."""
        state = WorkflowState()
        assert state.status == "pending"
        assert state.result is None
        assert state.error is None
        assert state.progress == 0.0
        assert state._cancelled is False

    def test_custom_initial_status(self):
        """Test workflow state with custom initial status."""
        state = WorkflowState(status="running")
        assert state.status == "running"

    def test_cancel(self):
        """Test cancelling a workflow."""
        state = WorkflowState(status="running")
        state.cancel()
        assert state._cancelled is True
        assert state.status == "cancelled"

    def test_to_dict(self):
        """Test converting workflow state to dictionary."""
        state = WorkflowState(status="completed")
        state.result = {"output": "test"}
        state.progress = 1.0
        d = state.to_dict()
        assert d["status"] == "completed"
        assert d["result"] == {"output": "test"}
        assert d["error"] is None
        assert d["progress"] == 1.0

    def test_to_dict_with_error(self):
        """Test converting failed workflow state to dictionary."""
        state = WorkflowState(status="failed")
        state.error = "Something went wrong"
        d = state.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "Something went wrong"


class TestGenerateWorkflowId:
    """Tests for workflow ID generation."""

    def test_generates_string(self):
        """Test that workflow ID is a string."""
        assert isinstance(generate_workflow_id(), str)

    def test_generates_8_chars(self):
        """Test that workflow ID is 8 characters."""
        assert len(generate_workflow_id()) == 8

    def test_generates_unique_ids(self):
        """Test that workflow IDs are unique."""
        ids = [generate_workflow_id() for _ in range(100)]
        assert len(set(ids)) == 100


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory with sample configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        (config_dir / "agents").mkdir()
        (config_dir / "swarms").mkdir()
        (config_dir / "graphs").mkdir()
        (config_dir / "tools").mkdir()
        (config_dir / "settings.yaml").write_text("defaults:\n  model: test\n")
        (config_dir / "agents" / "test_agent.yaml").write_text(
            "id: test_agent\nname: Test Agent\nmodel: test\nsystem_prompt: Test.\n"
        )
        (config_dir / "swarms" / "test_swarm.yaml").write_text(
            "id: test_swarm\nname: Test Swarm\nentry_point: a1\nagents:\n"
            "  - id: a1\n    name: A1\n    model: test\n    system_prompt: Test.\n"
        )
        (config_dir / "graphs" / "test_graph.yaml").write_text(
            "id: test_graph\nname: Test Graph\nnodes:\n"
            "  - id: n1\n    type: agent\n    agent_id: test_agent\nedges: []\n"
            "entry_points:\n  - n1\n"
        )
        yield config_dir


class TestMCPServer:
    """Tests for MCP server creation and tools."""

    @pytest.mark.asyncio
    async def test_create_mcp_server(self, temp_config_dir):
        """Test creating MCP server."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        assert agent.mcp is not None
        assert agent.mcp.name == "agent-module"

    @pytest.mark.asyncio
    async def test_get_capabilities_tool(self, temp_config_dir):
        """Test get_capabilities tool returns correct structure."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        caps = agent.get_capabilities()
        assert "deterministic_tools" in caps
        assert "swarms" in caps
        assert "graphs" in caps
        assert "agents" in caps

    @pytest.mark.asyncio
    async def test_health_check_tool(self, temp_config_dir):
        """Test health_check tool returns correct status."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        health = agent.health_check()
        assert health["status"] == "healthy"
