"""Tests for Graph registry."""

import pytest
from pathlib import Path
import tempfile

from factory.agent.registry.graphs import GraphRegistry


@pytest.fixture
def temp_graphs_dir():
    """Create a temporary graphs directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graphs_dir = Path(tmpdir)

        (graphs_dir / "pipeline.yaml").write_text("""
id: pipeline
name: Analysis Pipeline
nodes:
  - id: research
    type: swarm
    swarm_id: research_swarm
  - id: report
    type: agent
    agent_id: report_writer
edges:
  - source: research
    target: report
entry_points:
  - research
""")

        yield graphs_dir


class TestGraphRegistry:
    """Tests for GraphRegistry."""

    @pytest.mark.asyncio
    async def test_load_graphs(self, temp_graphs_dir):
        """Test loading graphs from directory."""
        registry = GraphRegistry(temp_graphs_dir)
        await registry.load()

        assert len(registry.graphs) == 1
        assert "pipeline" in registry.graphs

    @pytest.mark.asyncio
    async def test_get_graph(self, temp_graphs_dir):
        """Test getting graph by ID."""
        registry = GraphRegistry(temp_graphs_dir)
        await registry.load()

        graph = registry.get("pipeline")
        assert graph is not None
        assert graph.name == "Analysis Pipeline"
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    @pytest.mark.asyncio
    async def test_register_node_type(self, temp_graphs_dir):
        """Test registering custom node types."""
        registry = GraphRegistry(temp_graphs_dir)

        class CustomNode:
            pass

        registry.register_node_type("custom", CustomNode)
        assert registry.get_node_type("custom") == CustomNode
