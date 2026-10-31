"""Tests for optional MCP authoring tools.

These tools are intentionally disabled by default and require an explicit enable flag.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from collections.abc import Generator

import pytest

from factory.agent import SuperAgent
from factory.agent.authoring import AuthoringManager, AuthoringError


@pytest.fixture
def temp_config_dir_empty() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        (config_dir / "agents").mkdir()
        (config_dir / "swarms").mkdir()
        (config_dir / "graphs").mkdir()
        (config_dir / "tools").mkdir()
        yield config_dir


@pytest.mark.asyncio
async def test_authoring_tools_enabled_by_env_var(temp_config_dir_empty, monkeypatch):
    monkeypatch.setenv("SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "1")

    agent = SuperAgent(config_dir=str(temp_config_dir_empty))
    await agent.initialize()

    tool_names = {t.name for t in await agent.mcp.list_tools()}

    assert "authoring_status" in tool_names
    assert "list_config_items" in tool_names
    assert "write_config" in tool_names
    assert "read_config" in tool_names
    assert "delete_config" in tool_names
    assert "read_settings" in tool_names
    assert "write_settings" in tool_names
    assert "read_tool_module" in tool_names
    assert "write_tool_module" in tool_names
    assert "delete_tool_module" in tool_names
    assert "reload_config" in tool_names


@pytest.mark.asyncio
async def test_authoring_tools_do_not_escape_config_root(temp_config_dir_empty, monkeypatch):
    monkeypatch.setenv("SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "1")

    agent = SuperAgent(config_dir=str(temp_config_dir_empty))
    await agent.initialize()

    author = AuthoringManager(temp_config_dir_empty)
    with pytest.raises(AuthoringError):
        author.read_tool_module("../secrets")


@pytest.mark.asyncio
async def test_authoring_tools_stay_absent_without_any_gate(
    temp_config_dir_empty, monkeypatch,
):
    """Default (every surface var unset) denies every authoring action."""
    for variable in (
        "SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "FACTORY_AGENT_AUTHORING_SKILLS",
        "FACTORY_AGENT_AUTHORING_STEERING", "FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES",
        "FACTORY_AGENT_AUTHORING_CONFIG",
    ):
        monkeypatch.delenv(variable, raising=False)

    agent = SuperAgent(config_dir=str(temp_config_dir_empty))
    await agent.initialize()
    tool_names = {t.name for t in await agent.mcp.list_tools()}

    assert not tool_names & {
        "list_config_items", "read_config", "write_config", "delete_config",
        "read_settings", "write_settings", "read_tool_module", "write_tool_module",
        "delete_tool_module", "reload_config", "agent_create_agent", "agent_delete_agent",
        "agent_fork_agent", "agent_reset_agent", "agent_create_squad", "agent_delete_squad",
        "agent_add_skill", "agent_delete_skill",
        "agent_create_steering", "agent_update_steering", "agent_delete_steering",
    }
    # The probe and status stay registered so a UI can render the truth.
    assert {"agent_authoring_capabilities", "authoring_status"} <= tool_names
    status = await agent.mcp.get_tool("authoring_status")
    assert status.fn().data.enabled is False
