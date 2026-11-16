"""Swarm members resolve MCP tools like exact-tools personas (#416)."""
from __future__ import annotations

import re

import pytest

pytest.importorskip("langchain")  # local built-ins freeze a langchain version

from factory.agent.registry.defaults import SWARMS_TYPED
from factory.agent.runtime.adapters.capability_policy import effective_persona_scope
from factory.agent.runtime.agent_contracts import AgentConfig
from factory.agent.runtime.execution_manifest.compile_agents import compile_swarm
from factory.mcp_utils.interface import CapabilityScope

_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_BY_ID = {swarm.id: swarm for swarm in SWARMS_TYPED}


def _runtime_vars(swarm) -> dict[str, str]:
    """Run-time-bound prompt variables (target_app, run_id, ...) the caller supplies."""
    names = {n for a in swarm.agents for n in _VAR.findall(a.system_prompt)}
    return {name: f"<{name}>" for name in names}


def _needs_runtime_vars() -> list[str]:
    return sorted(s.id for s in SWARMS_TYPED if _runtime_vars(s))


@pytest.mark.parametrize("swarm_id", sorted(_BY_ID))
def test_every_registered_swarm_compiles_with_its_runtime_context(swarm_id: str) -> None:
    swarm = _BY_ID[swarm_id]
    manifest = compile_swarm(swarm.id, swarm, _runtime_vars(swarm))
    assert [m.id for m in manifest.members] == [a.id for a in swarm.agents]


def test_swarms_with_unbound_prompt_vars_fail_only_on_those_vars() -> None:
    """Not hidden: these swarms are runnable only once the caller binds the vars."""
    assert _needs_runtime_vars(), "expected some swarms to declare runtime vars"
    for swarm_id in _needs_runtime_vars():
        with pytest.raises(ValueError, match="unresolved prompt variables"):
            compile_swarm(swarm_id, _BY_ID[swarm_id], {})


@pytest.mark.parametrize("swarm_id", ["security-recon", "code-review"])
def test_member_mcp_tools_are_frozen_as_exact_scope(swarm_id: str) -> None:
    swarm = _BY_ID[swarm_id]
    for member, item in zip(compile_swarm(swarm.id, swarm, {}).members, swarm.agents):
        if not item.tools:
            continue
        assert member.tools.local == ()
        assert member.tools.mcp_mode == "explicit"
        assert member.tools.exact_tools is True
        assert member.tools.resolved_mcp_allowlist == tuple(item.tools)


def test_member_without_tools_keeps_inherit_scope() -> None:
    writer = compile_swarm("security-recon", _BY_ID["security-recon"], {}).members[-1]
    assert (writer.tools.mcp_mode, writer.tools.exact_tools) == ("inherit", False)
    assert writer.tools.resolved_mcp_allowlist == ()


def test_mixed_local_and_mcp_member_splits_tools() -> None:
    swarm = _BY_ID["security-recon"].model_copy(deep=True)
    swarm.agents[0].tools = ["think", "devtools_read_file"]
    tools = compile_swarm(swarm.id, swarm, {}).members[0].tools
    assert [t.name for t in tools.local] == ["think"]
    assert tools.resolved_mcp_allowlist == ("devtools_read_file",)


def test_frozen_member_scope_matches_runtime_persona_scope(monkeypatch) -> None:
    """The frozen allowlist is what effective_persona_scope grants a persona."""
    monkeypatch.setattr(
        "factory.mcp_server.interface.resolve_public_mcp_names", frozenset)
    item = _BY_ID["code-review"].agents[0]
    frozen = compile_swarm("code-review", _BY_ID["code-review"], {}).members[0].tools
    persona = AgentConfig(
        id=item.id, name=item.id, model="m", system_prompt="p",
        tools=list(item.tools), exact_tools=True)
    base = CapabilityScope.create(
        "p", {"devtools_read_file", "devtools_list_dir", "shell_exec"})
    scope = effective_persona_scope(base, persona)
    assert scope.tool_names == frozenset(frozen.resolved_mcp_allowlist)
