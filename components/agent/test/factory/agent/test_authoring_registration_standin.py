"""Authoring surfaces must register for ANY agent object, and never widen themselves.

Two invariants:
1. A tool catalog built from a stand-in agent (aggregator harnesses have no
   ``config_dir``) still registers the authoring modules.
2. No write on the config surface can raise the effective policy: the persisted
   ``settings.authoring.enabled`` switch is only consulted while NO per-surface
   flag is in play, and the config surface refuses to persist it as truthy.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

_GATE_VARS = (
    "SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "FACTORY_AGENT_AUTHORING_SKILLS",
    "FACTORY_AGENT_AUTHORING_STEERING", "FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES",
    "FACTORY_AGENT_AUTHORING_CONFIG",
)
_OTHER_SURFACE_TOOLS = {
    "agent_add_skill", "agent_delete_skill", "agent_create_steering",
    "agent_update_steering", "agent_delete_steering", "agent_create_agent",
    "agent_delete_agent", "agent_fork_agent", "agent_reset_agent",
}


def _standin(settings: dict | None = None, **extra) -> SimpleNamespace:
    """The aggregator harness shape: no ``config_dir``, registries as None."""
    return SimpleNamespace(
        settings={} if settings is None else settings, swarm_registry=None,
        agent_registry=None, graph_registry=None, tool_registry=None, workflows={},
        get_capabilities=lambda: {}, health_check=lambda: {}, **extra,
    )


def _clean(monkeypatch, tmp_path) -> None:
    for variable in _GATE_VARS:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("FACTORY_AGENT_CONFIG_DIR", str(tmp_path / "agent-config"))


def _tools(catalog) -> set[str]:
    return {tool.name for tool in asyncio.run(catalog.list_tools())}


def test_catalog_registers_for_a_standin_agent_without_config_dir(monkeypatch, tmp_path) -> None:
    from factory.agent.server import create_tool_catalog

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "all")

    names = _tools(create_tool_catalog(_standin()))
    assert {
        "authoring_status", "agent_authoring_capabilities", "write_config",
        "read_settings", "read_config",
    } <= names


def test_standin_agent_writes_use_the_durable_default_root(monkeypatch, tmp_path) -> None:
    from factory.agent.server import create_tool_catalog

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "all")
    root = tmp_path / "agent-config"

    catalog = create_tool_catalog(_standin())
    written = asyncio.run(catalog.call_tool("write_settings", {"settings": {"a": 1}}))
    assert written.structured_content["data"]["result"]["path"] == str(root / "settings.yaml")
    status = asyncio.run(catalog.call_tool("authoring_status", {}))
    assert status.structured_content["data"]["config_root"] == str(root)


def test_config_grant_cannot_widen_any_other_surface(monkeypatch, tmp_path) -> None:
    """The escalation the reviewer proved: config-only grant + persisted switch."""
    from factory.agent.server import create_tool_catalog

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "write")
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "none")

    escalating = {"authoring": {"enabled": True}}
    catalog = create_tool_catalog(_standin())
    denial = asyncio.run(catalog.call_tool("write_settings", {"settings": escalating}))
    assert denial.structured_content["data"]["result"]["error"] == "authoring_gate_immutable"

    # Even with the switch already persisted (a fresh process reading it back),
    # no surface flag-less surface may be opened by it.
    reopened = create_tool_catalog(_standin(settings=escalating))
    names = _tools(reopened)
    assert "write_config" in names
    assert _OTHER_SURFACE_TOOLS.isdisjoint(names)


def test_persisted_switch_only_applies_while_no_surface_flag_is_set(monkeypatch, tmp_path) -> None:
    from factory.agent.authoring import authoring_policy

    _clean(monkeypatch, tmp_path)
    switch = {"authoring": {"enabled": True}}
    assert authoring_policy(switch).allows("skills", "add")

    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "delete")
    narrowed = authoring_policy(switch)
    assert narrowed.allows("skills", "delete") and not narrowed.allows("skills", "add")
    assert not narrowed.allows("agent_templates", "create")
    assert not narrowed.allows("config", "read")


def test_legacy_switch_is_still_the_blanket_env_switch(monkeypatch, tmp_path) -> None:
    """Env is operator-owned (unwritable from inside), so it keeps its meaning."""
    from factory.agent.authoring import authoring_policy

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "write")
    monkeypatch.setenv("SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "true")

    policy = authoring_policy({})
    assert policy.allows("config", "write") and policy.allows("skills", "add")
    assert policy.allows("agent_templates", "reset")
