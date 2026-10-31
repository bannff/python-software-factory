"""The capability probe must agree with the gates by construction."""
from __future__ import annotations

import asyncio

import pytest

from factory.agent.authoring.policy import LEGACY_VARIABLE, SURFACE_VARIABLES

# (surface, action) -> the tool whose presence that pair governs.
_TOOLS: dict[tuple[str, str], str] = {
    ("skills", "add"): "agent_add_skill",
    ("skills", "delete"): "agent_delete_skill",
    ("steering", "create"): "agent_create_steering",
    ("steering", "update"): "agent_update_steering",
    ("steering", "delete"): "agent_delete_steering",
    ("agent_templates", "create"): "agent_create_agent",
    ("agent_templates", "delete"): "agent_delete_agent",
    ("agent_templates", "fork"): "agent_fork_agent",
    ("agent_templates", "reset"): "agent_reset_agent",
    ("config", "read"): "list_config_items",
    ("config", "write"): "write_config",
}

_COMBOS: list[dict[str, str]] = [
    {},
    {"FACTORY_AGENT_AUTHORING_SKILLS": "delete"},
    {"FACTORY_AGENT_AUTHORING_STEERING": "all"},
    {"FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES": "fork,reset"},
    {"FACTORY_AGENT_AUTHORING_CONFIG": "read"},
    {"FACTORY_AGENT_AUTHORING_CONFIG": "write",
     "FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES": "none"},
    {LEGACY_VARIABLE: "on"},
    {"FACTORY_AGENT_AUTHORING_STEERING": "create,typo"},
]


@pytest.fixture
def gates(monkeypatch, tmp_path):
    monkeypatch.delenv(LEGACY_VARIABLE, raising=False)
    for variable in SURFACE_VARIABLES.values():
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("FACTORY_AGENT_CONFIG_DIR", str(tmp_path / "agent-config"))
    return monkeypatch


def _catalog_tools_and_probe() -> tuple[set[str], dict]:
    from factory.agent.server import create_tool_catalog

    catalog = create_tool_catalog()
    names = {tool.name for tool in asyncio.run(catalog.list_tools())}
    probe = asyncio.run(catalog.call_tool("agent_authoring_capabilities", {}))
    return names, probe.structured_content["data"]


@pytest.mark.parametrize("env", _COMBOS, ids=lambda env: ",".join(env.values()) or "unset")
def test_probe_agrees_with_every_gate(gates, env: dict[str, str]) -> None:
    for variable, value in env.items():
        gates.setenv(variable, value)
    names, data = _catalog_tools_and_probe()
    assert "agent_authoring_capabilities" in names
    for (surface, action), tool in _TOOLS.items():
        assert data[surface][action] is (tool in names), (surface, action, tool)


def test_probe_reports_roots_and_source(gates, tmp_path) -> None:
    gates.setenv("FACTORY_AGENT_SKILLS_DIR", str(tmp_path / "skills"))
    _names, data = _catalog_tools_and_probe()
    assert data["roots"]["skills"] == {"path": str((tmp_path / "skills").resolve()), "source": "env"}
    assert data["roots"]["config"] == {
        "path": str((tmp_path / "agent-config").resolve()), "source": "env",
    }
    assert data["roots"]["steering"]["source"] == "default"
    assert data["roots"]["steering"]["path"].endswith(".storage/agent-steering")


def test_probe_is_absent_from_no_registration_and_never_denies_itself(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "none")
    names, data = _catalog_tools_and_probe()
    assert "agent_authoring_capabilities" in names
    assert data["config"] == {"read": False, "write": False}
    assert data["skills"] == {
        "add": False, "create": False, "update": False,
        "delete": False, "fork": False, "reset": False,
    }


@pytest.mark.asyncio
async def test_status_and_probe_report_the_root_writes_land_in(
    monkeypatch, tmp_path,
) -> None:
    """An explicitly constructed agent reports ITS config dir, not the env one."""
    monkeypatch.setenv("FACTORY_AGENT_CONFIG_DIR", str(tmp_path / "declared"))
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "write")
    from factory.agent.agent import SuperAgent

    config_dir = tmp_path / "explicit-config"
    agent = SuperAgent(config_dir=str(config_dir))
    await agent.initialize()

    probe = await agent.mcp.call_tool("agent_authoring_capabilities", {})
    assert probe.structured_content["data"]["roots"]["config"] == {
        "path": str(config_dir), "source": "default",
    }
    status = await agent.mcp.call_tool("authoring_status", {})
    assert status.structured_content["data"]["config_root"] == str(config_dir)
    written = await agent.mcp.call_tool("write_settings", {"settings": {"a": 1}})
    assert written.structured_content["data"]["result"]["path"] == str(
        config_dir / "settings.yaml"
    )

