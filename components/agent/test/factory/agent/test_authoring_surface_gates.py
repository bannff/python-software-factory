"""Per-surface authoring gates: flag parsing, precedence, and tool absence.

The gate admits every token a surface declares, so delete-without-create and
create-without-delete are both expressible; a malformed value denies the whole
surface (a typo must never widen) and never falls through to the blanket switch.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from factory.agent.authoring.policy import (
    LEGACY_VARIABLE, SURFACE_ACTIONS, SURFACE_VARIABLES, authoring_policy,
)

_ALL = [(surface, action) for surface, actions in SURFACE_ACTIONS.items() for action in actions]


@pytest.fixture
def gates(monkeypatch, tmp_path):
    """Clear every gate var and pin the config root away from the repo."""
    monkeypatch.delenv(LEGACY_VARIABLE, raising=False)
    for variable in SURFACE_VARIABLES.values():
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("FACTORY_AGENT_CONFIG_DIR", str(tmp_path / "agent-config"))
    return monkeypatch


def _catalog_tools() -> set[str]:
    from factory.agent.server import create_tool_catalog

    catalog = create_tool_catalog()
    return {tool.name for tool in asyncio.run(catalog.list_tools())}


def test_unset_surfaces_deny_every_action(gates) -> None:
    policy = authoring_policy({})
    assert not policy.any_allowed()
    assert all(not policy.allows(surface, action) for surface, action in _ALL)
    assert policy.malformed == ()
    assert _catalog_tools().isdisjoint(
        name for surface, action in _ALL for name in
        ["agent_add_skill", "agent_delete_skill", "agent_create_steering",
         "agent_update_steering", "agent_delete_steering", "agent_create_agent",
         "agent_delete_agent", "agent_fork_agent", "agent_reset_agent",
         "write_config", "list_config_items"]
    )


def test_surface_flag_selects_only_its_own_tokens(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add")
    policy = authoring_policy({})
    assert policy.allows("skills", "add") and not policy.allows("skills", "delete")
    for surface in ("steering", "agent_templates", "config"):
        assert not any(policy.allows(surface, action) for action in SURFACE_ACTIONS[surface])


def test_tokens_are_trimmed_and_lowercased(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", " Add , DELETE ")
    policy = authoring_policy({})
    assert policy.allows("skills", "add") and policy.allows("skills", "delete")
    assert policy.malformed == ()


def test_none_and_all_tokens(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_STEERING", "none")
    gates.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "all")
    policy = authoring_policy({})
    assert not any(policy.allows("steering", action) for action in SURFACE_ACTIONS["steering"])
    assert all(policy.allows("config", action) for action in SURFACE_ACTIONS["config"])


def test_blanks_resolve_as_unset_and_fall_through(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "   ")
    gates.setenv(LEGACY_VARIABLE, "yes")
    policy = authoring_policy({})
    assert policy.allows("skills", "add") and policy.allows("config", "write")
    assert policy.malformed == ()


def test_unknown_token_denies_the_whole_surface_and_warns(gates, caplog) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add,typo")
    gates.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "read")
    with caplog.at_level(logging.WARNING, logger="factory.agent.authoring.policy"):
        policy = authoring_policy({})
    assert policy.malformed == ("skills",)
    assert not any(policy.allows("skills", action) for action in SURFACE_ACTIONS["skills"])
    assert policy.allows("config", "read")
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "FACTORY_AGENT_AUTHORING_SKILLS" in message and "typo" in message
    assert "add" in message and "delete" in message


def test_malformed_value_never_falls_through_to_the_blanket_switch(gates) -> None:
    gates.setenv(LEGACY_VARIABLE, "true")
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add,typo")
    policy = authoring_policy({})
    assert not any(policy.allows("skills", action) for action in SURFACE_ACTIONS["skills"])
    assert policy.allows("steering", "create") and policy.allows("config", "write")


def test_specific_flag_beats_blanket_switch_and_settings(gates) -> None:
    gates.setenv(LEGACY_VARIABLE, "1")
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "none")
    policy = authoring_policy({"authoring": {"enabled": True}})
    assert not policy.allows("skills", "add")
    assert policy.allows("config", "write") and policy.allows("agent_templates", "reset")


def test_settings_authoring_enabled_is_the_last_fallback(gates) -> None:
    assert authoring_policy({"authoring": {"enabled": True}}).allows("steering", "update")
    assert not authoring_policy({"authoring": {"enabled": False}}).any_allowed()


def test_one_malformed_flag_logs_exactly_one_warning_per_catalog(gates, caplog) -> None:
    """One catalog registers five authoring modules; a typo must warn once."""
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add,typo")
    gates.setenv("FACTORY_AGENT_AUTHORING_STEERING", "create,bogus")
    with caplog.at_level(logging.WARNING, logger="factory.agent.authoring.policy"):
        _catalog_tools()
    warnings = [
        record for record in caplog.records
        if "FACTORY_AGENT_AUTHORING_" in record.getMessage()
    ]
    assert len(warnings) == 2, [record.getMessage() for record in warnings]
    assert len({record.getMessage() for record in warnings}) == 2


def test_skills_deletion_only_registers_the_delete_tool(gates) -> None:
    """The requested demonstration: delete-without-create, and the mirror."""
    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "delete")
    names = _catalog_tools()
    assert "agent_delete_skill" in names
    assert "agent_add_skill" not in names
    assert {"agent_list_skills", "agent_read_skill", "agent_authoring_capabilities"} <= names

    gates.setenv("FACTORY_AGENT_AUTHORING_SKILLS", "add")
    names = _catalog_tools()
    assert "agent_add_skill" in names
    assert "agent_delete_skill" not in names


def test_create_without_fork_or_delete_is_expressible(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES", "create")
    names = _catalog_tools()
    assert "agent_create_agent" in names
    assert {"agent_delete_agent", "agent_fork_agent", "agent_reset_agent"}.isdisjoint(names)

    gates.setenv("FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES", "fork")
    names = _catalog_tools()
    assert "agent_fork_agent" in names
    assert {"agent_create_agent", "agent_delete_agent", "agent_reset_agent"}.isdisjoint(names)


def test_steering_update_without_create_or_delete_is_expressible(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_STEERING", "update")
    names = _catalog_tools()
    assert "agent_update_steering" in names
    assert {"agent_create_steering", "agent_delete_steering"}.isdisjoint(names)


def test_config_write_only_registers_writes(gates) -> None:
    gates.setenv("FACTORY_AGENT_AUTHORING_CONFIG", "write")
    names = _catalog_tools()
    assert {"write_config", "delete_config", "write_settings", "reload_config"} <= names
    assert {"list_config_items", "read_config", "read_settings", "read_tool_module"}.isdisjoint(names)
