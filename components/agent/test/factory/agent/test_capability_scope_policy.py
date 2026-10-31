"""Persona and delegation capability attenuation invariants."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given, strategies as st

from factory.agent.registry.defaults_dataset_research import DATASET_RESEARCHER
from factory.agent.runtime.adapters.capability_policy import effective_persona_scope
from factory.mcp_utils.interface import CapabilityScope

SPAWN = {"agent_spawn_subagent", "agent_spawn_swarm", "agent_spawn_graph"}
BASE = SPAWN | {"sandbox_execute", "blockchain_transfer", "dataset_get_job"}


def _persona(*, tools=(), exact=False):
    return SimpleNamespace(tools=list(tools), exact_tools=exact)


@pytest.fixture(autouse=True)
def canonicalizer(monkeypatch):
    aliases = {
        "sandbox.execute": "sandbox_execute",
        "sandbox_execute": "sandbox_execute",
        "agent_spawn_subagent": "agent_spawn_subagent",
    }

    def resolve(names):
        result = set()
        for name in names:
            if name not in aliases:
                raise ValueError(f"unknown: {name}")
            result.add(aliases[name])
        return frozenset(result)

    monkeypatch.setattr("factory.mcp_server.interface.resolve_public_mcp_names", resolve)


def test_root_non_exact_keeps_spawn_but_delegated_non_exact_loses_all_spawn() -> None:
    root = CapabilityScope.create("p", BASE)
    assert SPAWN <= effective_persona_scope(root, _persona()).tool_names
    child = CapabilityScope.create("p", BASE, delegation_depth=1)
    effective = effective_persona_scope(child, _persona())
    assert effective.tool_names == BASE - SPAWN


def test_dataset_exact_empty_has_zero_capabilities() -> None:
    base = CapabilityScope.create("p", BASE)
    assert effective_persona_scope(base, DATASET_RESEARCHER).tool_names == frozenset()


def test_exact_alias_subset_ignores_known_local_and_unknown_mcp_fails() -> None:
    base = CapabilityScope.create("p", BASE)
    effective = effective_persona_scope(
        base, _persona(tools=["think", "sandbox.execute"], exact=True),
    )
    assert effective.tool_names == frozenset({"sandbox_execute"})
    with pytest.raises(ValueError, match="unknown"):
        effective_persona_scope(
            base, _persona(tools=["not_a_local_or_mcp_tool"], exact=True),
        )


def test_narrow_parent_cannot_widen_child_or_inherit_spawn() -> None:
    parent = CapabilityScope.create("p", {"agent_spawn_subagent"}, delegation_depth=1)
    child = effective_persona_scope(parent, _persona())
    assert child.tool_names == frozenset()
    assert not child.tool_names & {"sandbox_execute", "blockchain_transfer"}


def test_exact_spawn_survives_only_when_explicit_and_parent_owned() -> None:
    parent = CapabilityScope.create(
        "p", {"agent_spawn_subagent", "sandbox_execute"}, delegation_depth=1,
    )
    explicit = effective_persona_scope(
        parent, _persona(tools=["agent_spawn_subagent"], exact=True),
    )
    assert explicit.tool_names == frozenset({"agent_spawn_subagent"})
    absent = CapabilityScope.create("p", {"sandbox_execute"}, delegation_depth=1)
    assert not effective_persona_scope(
        absent, _persona(tools=["agent_spawn_subagent"], exact=True),
    ).tool_names


@given(st.sets(st.sampled_from(sorted(BASE))))
def test_effective_child_scope_is_always_parent_subset(names: set[str]) -> None:
    parent = CapabilityScope.create("p", names, delegation_depth=1)
    child = effective_persona_scope(parent, _persona())
    assert child.tool_names <= parent.tool_names
