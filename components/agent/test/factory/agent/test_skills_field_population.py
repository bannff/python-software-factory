"""Per-node ``skills`` population audit (bd:python-factory-2tgo1).

strands-expert verdict ``1c5df3c7`` Q5.iv: every defaults_*.py role
prompt that explicitly tells the model to invoke the ``skills`` tool
must populate ``skills`` on its ``AgentNodeRef`` / ``SwarmAgentConfig``
in the same diff. This test is the regression gate.

Mirrors the 8-test pattern in ``test_chat_persona_registry.py``
(bd:python-factory-hadbi.1) — pure data, no SDK dependency.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from factory.agent.registry.defaults import GRAPHS_TYPED, SWARMS_TYPED
from factory.agent.runtime.registry_contracts import (
    AgentNodeRef, SwarmAgentConfig, SwarmConfig, WorkflowConfig,
)


def _prompt_mentions_skills_tool(prompt: str) -> bool:
    """True iff the prompt tells the model to call the ``skills`` tool.
    Single source of truth for Tier-A (specialist) vs Tier-D (coord)."""
    if not prompt:
        return False
    if re.search(r"call\s+(?:the\s+)?skills\s*(tool|\()", prompt):
        return True
    if re.search(r"\bActivate\s+(?:it\s+)?(?:via|now)\s+", prompt):
        return bool(re.search(r"skills?\s+tool", prompt))
    return False


def _walk_agent_nodes() -> list[tuple[str, str, AgentNodeRef]]:
    """Yield (graph_id, node_id, node) for every AgentNodeRef in
    every registered graph (covers all hybrid/graph-only variants)."""
    out: list[tuple[str, str, AgentNodeRef]] = []
    for g in GRAPHS_TYPED:
        for n in (getattr(g, "nodes", None) or []):
            if isinstance(n, AgentNodeRef):
                out.append((g.id, n.id, n))
    return out


def _walk_swarm_agents() -> list[tuple[str, str, SwarmAgentConfig]]:
    """Yield (swarm_id, agent_id, agent) for every SwarmAgentConfig."""
    out: list[tuple[str, str, SwarmAgentConfig]] = []
    for s in SWARMS_TYPED:
        if isinstance(s, SwarmConfig):
            for ag in s.agents:
                out.append((s.id, ag.id, ag))
    return out


def _walk_workflow_tasks() -> list[tuple[str, str, dict[str, Any]]]:
    """Yield (workflow_id, task_id, task_dict) for every registered
    workflow factory output. Workflow tasks are runtime dicts;
    ``_workflow_manager.py`` plumbs them through the same per-node
    skills attach as graph nodes."""
    from factory.agent.registry.factories import get_factory

    out: list[tuple[str, str, dict[str, Any]]] = []
    ctx = {"vuln_class": "IDOR", "target_app": "x"}
    for g in GRAPHS_TYPED:
        if not isinstance(g, WorkflowConfig):
            continue
        try:
            factory = get_factory(g.factory)
        except Exception:
            continue
        try:
            tasks = factory(ctx)
        except TypeError:
            tasks = factory({})
        for t in tasks:
            out.append((g.id, t.get("task_id", ""), t))
    return out


# Tier-A registrations whose prompts invoke the skills tool. Source:
# strands-expert verdict ``1c5df3c7`` — 17 affected files.
_AFFECTED_REGISTRATION_IDS = {
    "rt-scan-idor", "rt-scan-idor-hybrid",
    "rt-sast-scan-hybrid", "rt-sandbox-setup-graph",
    "rt-sandbox-setup-hybrid", "rt-sast-sonnet",
    "rt-sast-scan", "sandbox-setup", "sast", "dast",
    "rt-sast-scan-swarm", "rt-scan-idor-swarm-v2",
    "rt-scan-vulns", "rt-prove-vulns",
}


# ----------------------------------------------------------------------
# Per-registration canaries (parametrize by walker output).
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "graph_id,node_id,node",
    _walk_agent_nodes(),
    ids=lambda x: x.id if hasattr(x, "id") else str(x),
)
def test_agent_node_skills_match_prompt(
    graph_id: str, node_id: str, node: AgentNodeRef,
) -> None:
    """AgentNodeRef whose prompt invokes skills tool ⇒ non-empty skills."""
    if not _prompt_mentions_skills_tool(node.system_prompt or ""):
        return  # Tier-D coord role — empty skills is correct.
    assert node.skills, (
        f"AgentNodeRef[{graph_id}/{node_id}] prompt invokes the skills "
        f"tool but skills=[] — populate per bd:python-factory-2tgo1."
    )


@pytest.mark.parametrize(
    "swarm_id,agent_id,agent",
    _walk_swarm_agents(),
    ids=lambda x: x.id if hasattr(x, "id") else str(x),
)
def test_swarm_agent_skills_match_prompt(
    swarm_id: str, agent_id: str, agent: SwarmAgentConfig,
) -> None:
    """SwarmAgentConfig whose prompt invokes skills tool ⇒ non-empty."""
    if not _prompt_mentions_skills_tool(agent.system_prompt or ""):
        return
    assert agent.skills, (
        f"SwarmAgentConfig[{swarm_id}/{agent_id}] prompt invokes the "
        f"skills tool but skills=[] — populate per bd:python-factory-2tgo1."
    )


def test_workflow_tasks_carry_skills_field() -> None:
    """Workflow factories must emit task dicts with a ``skills`` key
    (empty or non-empty). Missing key ⇒ legacy whole-dir fallback,
    which means the migration is incomplete (bd:python-factory-2tgo1)."""
    tasks = _walk_workflow_tasks()
    assert tasks, "no workflow factories produced tasks — registry empty?"
    for wf_id, task_id, task in tasks:
        assert "skills" in task, (
            f"Workflow task[{wf_id}/{task_id}] missing 'skills' key — "
            f"falls back to whole-dir; migrate per bd:python-factory-2tgo1."
        )
        assert isinstance(task["skills"], list), (
            f"Workflow task[{wf_id}/{task_id}].skills must be a list, "
            f"got {type(task['skills']).__name__}"
        )


def test_audit_coverage_no_unmigrated_registrations() -> None:
    """Every strands-expert-listed registration must be reachable via
    the walkers above. If any are missing the registry has drifted —
    update ``_AFFECTED_REGISTRATION_IDS`` or investigate."""
    seen_ids = {gid for gid, _, _ in _walk_agent_nodes()}
    seen_ids |= {sid for sid, _, _ in _walk_swarm_agents()}
    seen_ids |= {wid for wid, _, _ in _walk_workflow_tasks()}
    missing = _AFFECTED_REGISTRATION_IDS - seen_ids
    assert not missing, (
        f"strands-expert verdict 1c5df3c7 listed these registrations "
        f"but they are unreachable: {sorted(missing)}"
    )


def test_agent_node_ref_skills_default_empty() -> None:
    """AgentNodeRef.skills defaults to [] (additive, bd:2tgo1)."""
    node = AgentNodeRef(id="x", type="agent", description="",
                        system_prompt="hi")
    assert node.skills == []
    assert AgentNodeRef.model_validate(node.model_dump()).skills == []


def test_swarm_agent_config_skills_default_empty() -> None:
    """SwarmAgentConfig.skills defaults to [] (additive, bd:2tgo1)."""
    ag = SwarmAgentConfig(id="x", model="us.amazon.nova-lite-v1:0",
                          system_prompt="hi")
    assert ag.skills == []
    assert SwarmAgentConfig.model_validate(ag.model_dump()).skills == []
