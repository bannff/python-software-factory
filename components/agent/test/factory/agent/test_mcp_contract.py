"""Tests for agent MCP contract tools.

Every MCP-enabled brick MUST expose:
- get_capabilities() - Machine-readable feature list
- health_check() - Fast readiness probe
- describe_config_schema() - JSON schema for configuration

Note: Agent uses create_mcp_server() factory pattern, so we test via SuperAgent.
"""

from __future__ import annotations

import asyncio

import pytest
from pathlib import Path
import tempfile

from factory.agent import SuperAgent


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
        yield config_dir


async def _get_tool(mcp, name: str):
    """Get a tool by name from the MCP server."""
    return await mcp.get_tool(name)


class TestGetCapabilities:
    """Tests for get_capabilities contract tool."""

    @pytest.mark.asyncio
    async def test_tool_registered(self, temp_config_dir) -> None:
        """get_capabilities tool must be registered."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        tool = await _get_tool(agent.mcp, "get_capabilities")
        assert tool is not None

    @pytest.mark.asyncio
    async def test_returns_dict(self, temp_config_dir) -> None:
        """get_capabilities must return a dictionary."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.get_capabilities()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_has_tools(self, temp_config_dir) -> None:
        """Capabilities must include tools info."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.get_capabilities()
        assert "deterministic_tools" in result

    @pytest.mark.asyncio
    async def test_has_swarms(self, temp_config_dir) -> None:
        """Capabilities must include swarms info."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.get_capabilities()
        assert "swarms" in result

    @pytest.mark.asyncio
    async def test_has_graphs(self, temp_config_dir) -> None:
        """Capabilities must include graphs info."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.get_capabilities()
        assert "graphs" in result


class TestHealthCheck:
    """Tests for health_check contract tool."""

    @pytest.mark.asyncio
    async def test_tool_registered(self, temp_config_dir) -> None:
        """health_check tool must be registered."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        tool = await _get_tool(agent.mcp, "health_check")
        assert tool is not None

    @pytest.mark.asyncio
    async def test_returns_dict(self, temp_config_dir) -> None:
        """health_check must return a dictionary."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.health_check()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_has_status_field(self, temp_config_dir) -> None:
        """health_check must include status."""
        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        result = agent.health_check()
        assert "status" in result

    @pytest.mark.asyncio
    async def test_health_dict_fits_strict_output_contract(self, temp_config_dir) -> None:
        """Regression (live 2026-09-30): SuperAgent.health_check() gained
        ``squads_loaded`` (squads feature port) while the strict
        HealthOutput contract (extra="forbid") did not — every
        agent_health_check call flattened to tool_execution_failed. The
        dict the runtime produces must always validate against the
        contract the MCP boundary enforces."""
        from factory.agent.mcp.contracts.discovery import HealthOutput

        agent = SuperAgent(config_dir=str(temp_config_dir))
        await agent.initialize()
        HealthOutput.model_validate(agent.health_check())
