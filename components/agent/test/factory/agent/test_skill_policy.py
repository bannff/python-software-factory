"""Owner-scoped skill enablement: policy, store, MCP boundary, manifest consumer."""
from __future__ import annotations

import asyncio

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")
from pydantic import ValidationError

from factory.agent.mcp import skill_policy as mcp
from factory.agent.registry.defaults import AGENTS_TYPED
from factory.agent.runtime.adapters.skill_policy_store import SqliteSkillPolicyStore
from factory.agent.runtime.background.persona_graph import persona_graph
from factory.agent.runtime.execution_manifest.compile_agents import owner_enabled_skills
from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest
from factory.agent.runtime.skill_policy import InMemorySkillPolicyStore, SkillPolicy, StaleSkillPolicy
from factory.mcp_utils.interface import get_service, reset_envelope, set_envelope, set_service
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

OWNER = {"tenant_id": "t", "principal_id": "owner"}


class Registry:
    def get(self, agent_id: str):
        return next((item for item in AGENTS_TYPED if item.id == agent_id), None)


def test_policy_validates_ids_and_applies_subtraction() -> None:
    policy = SkillPolicy(disabled_skills=("can-analyst",))
    assert policy.apply(["cdk-analysis", "can-analyst", "x"]) == ["cdk-analysis", "x"]
    for bad in (("Bad Id",), ("a", "a"), ("",)):
        with pytest.raises(ValidationError):
            SkillPolicy(disabled_skills=bad)


def test_sqlite_store_is_owner_scoped_with_cas(tmp_path) -> None:
    store = SqliteSkillPolicyStore(tmp_path / "p.db")
    assert store.get("t", "a") == SkillPolicy()
    first = store.update("t", "a", 0, disabled_skills=("can-analyst",))
    assert first.revision == 1 and store.get("t", "b") == SkillPolicy()
    with pytest.raises(StaleSkillPolicy):
        store.update("t", "a", 0, disabled_skills=())
    assert store.update("t", "a", 1, disabled_skills=()).revision == 2


def _tools(store, known):
    catalog = ToolCatalog("agent")
    mcp.register(catalog, store, lambda: known)
    return {tool.name: tool for tool in asyncio.run(catalog.list_tools())}


def test_mcp_requires_owner_and_refuses_unknown_skill() -> None:
    tools = _tools(InMemorySkillPolicyStore(), ["cdk-analysis"])
    assert tools["get_skill_policy"].fn().error == "agent_skill_policy_unavailable"
    token = set_envelope(dict(OWNER))
    try:
        assert tools["get_skill_policy"].fn().data.disabled_skills == []
        bad = tools["update_skill_policy"].fn(disabled_skills=["nope"], expected_revision=0)
        assert bad.error == "agent_skill_policy_unknown_skill"
        good = tools["update_skill_policy"].fn(disabled_skills=["cdk-analysis"], expected_revision=0)
        assert good.ok and good.data.revision == 1
        stale = tools["update_skill_policy"].fn(disabled_skills=[], expected_revision=0)
        assert stale.error == "agent_skill_policy_conflict"
    finally:
        reset_envelope(token)


def test_manifest_drops_owner_disabled_skills_and_changes_digest() -> None:
    persona = next(item for item in AGENTS_TYPED if item.skills)
    store = InMemorySkillPolicyStore()
    store.update("t", "owner", 0, disabled_skills=(persona.skills[0],))
    previous = get_service("agent_skill_policy_store")
    set_service("agent_skill_policy_store", store)
    graph = persona_graph(Registry(), persona.id)
    try:
        unscoped = prepare_execution_manifest(graph, "task", {})
        token = set_envelope(dict(OWNER))
        try:
            scoped = prepare_execution_manifest(graph, "task", {})
        finally:
            reset_envelope(token)
    finally:
        set_service("agent_skill_policy_store", previous)
    assert persona.skills[0] in unscoped.nodes[0].skills.names
    assert persona.skills[0] not in scoped.nodes[0].skills.names
    assert unscoped.digest != scoped.digest, "frozen evidence must reflect what actually attached"
    assert owner_enabled_skills(["anything"]) == ["anything"], "no ambient owner → no-op"
