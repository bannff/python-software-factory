"""Tests for persona → strands AgentSkills plugin projection (issue #104).

Covers: persona with skills registers the plugin's ``skills`` tool on the
built agent; skill-policy disable filtering; missing-dir skip vs loud-fail;
on-demand SKILL.md loading through the plugin tool (progressive disclosure —
the system prompt only ever carries metadata, never the body).
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_skills import persona_skills
from factory.agent.runtime.skill_policy import SkillPolicy

from ._strands_contract_fakes import NullClient, RepliedModel, _chat

# Real skill shipped in the brick: components/agent/src/factory/agent/skills/<id>/
# test file → test/factory/agent/... → parents: [agent, factory, test, agent(brick), components]
_REAL_SKILL = (
    Path(__file__).resolve().parents[3] / "src" / "factory" / "agent"
    / "skills" / "pentest-ops"
)
# The brick must ship the skill (private-tree invariant); a raw module-level
# assert would error every collection in a tree where the skill is absent.
if not (_REAL_SKILL / "SKILL.md").is_file():
    pytest.skip(
        f"real skill absent from this tree: {_REAL_SKILL}",
        allow_module_level=True,
    )


class _Persona:
    """Minimal AgentConfig stand-in (id + skills only)."""

    def __init__(self, id_: str, skills: list[str]) -> None:
        self.id = id_
        self.skills = skills


def test_persona_with_two_skills_registers_skills_tool() -> None:
    plugins = persona_skills(_Persona("p1", ["sandbox-ops", "pentest-ops"]))
    assert len(plugins) == 1
    agent = _agent_with(plugins)
    assert "skills" in agent.tool_registry.registry


async def _invoke_tool(tool: object, agent: object, input_: dict) -> str:
    """Invoke the plugin tool the way the registry does, with ToolContext."""
    from strands.types.tools import ToolContext

    tool_use: dict = {"toolUseId": "t1", "name": "skills", "input": input_}
    context = ToolContext(tool_use=tool_use, agent=agent, invocation_state={})
    tool_result = None
    async for event in tool.stream(tool_use, {}, _tool_context=context):
        tool_result = event
    blocks = tool_result.tool_result["content"]
    return "".join(b["text"] for b in blocks if isinstance(b, dict) and "text" in b)


def test_policy_disabled_skill_is_filtered() -> None:
    policy = SkillPolicy(disabled_skills=("pentest-ops",))
    plugins = persona_skills(
        _Persona("p2", ["sandbox-ops", "pentest-ops"]), policy)
    assert len(plugins) == 1
    agent = _agent_with(plugins)
    tool = agent.tool_registry.registry["skills"]
    not_found = asyncio.run(_invoke_tool(tool, agent, {"skill_name": "pentest-ops"}))
    assert "not found" in not_found
    loaded = asyncio.run(_invoke_tool(tool, agent, {"skill_name": "sandbox-ops"}))
    assert "Sandbox" in loaded


def test_missing_skill_dir_skipped_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        plugins = persona_skills(_Persona("p3", ["no-such-skill", "sandbox-ops"]))
    assert len(plugins) == 1
    assert any("no-such-skill" in rec.message for rec in caplog.records)


def test_all_skills_missing_fails_loudly() -> None:
    with pytest.raises(FileNotFoundError, match="ghost-skill"):
        persona_skills(_Persona("p4", ["ghost-skill"]))


def test_empty_persona_skills_yields_no_plugins() -> None:
    assert persona_skills(_Persona("p5", [])) == []


@pytest.mark.asyncio
async def test_skill_md_loads_on_demand(tmp_path: Path) -> None:
    """Copy a real skill into tmp and load its body through the plugin tool."""
    skill_dir = tmp_path / "pentest-ops"
    shutil.copytree(_REAL_SKILL, skill_dir)
    from strands.vended_plugins.skills import AgentSkills
    plugin = AgentSkills(skills=[str(skill_dir)])
    agent = _agent_with([plugin])
    tool = agent.tool_registry.registry["skills"]
    result = await _invoke_tool(tool, agent, {"skill_name": "pentest-ops"})
    assert "Penetration Testing Operations" in result


def _agent_with(plugins: list) -> object:
    """Build a real strands Agent (fake model) with the given plugins."""
    from strands import Agent

    return Agent(
        model=RepliedModel(), callback_handler=None, plugins=plugins,
    )


def test_chat_agent_mounts_skills_tool() -> None:
    """Live-ish: the chat facade's built agent carries the skills tool for a
    persona owning skills."""
    chat = _chat(RepliedModel())

    async def _build() -> object:
        return await chat._agent_for("skills-thread", "companion-x-default")

    agent = asyncio.run(_build())
    assert "skills" in agent.tool_registry.registry
