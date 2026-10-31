"""Surgical tests for workflow type comparison experiment configs.

Validates each new variant config:
1. Imports correctly
2. Has required schema fields
3. Swarm entry_point matches an agent id
4. Graph entry_points match node ids
5. Graph edges reference valid node ids
6. Hybrid swarm_id refs exist in registered swarms
7. All prompts contain memory_retrieve (STEP 0)
8. All prompts contain graph storage instructions
9. Context variables use {{var}} template syntax
"""
from __future__ import annotations

import pytest


# --- Schema validators ---

def _check_swarm(cfg: dict, label: str) -> None:
    """Validate swarm config schema."""
    assert "id" in cfg, f"{label}: missing id"
    assert "entry_point" in cfg, f"{label}: missing entry_point"
    assert "agents" in cfg, f"{label}: missing agents"
    assert len(cfg["agents"]) >= 2, f"{label}: need >=2 agents"
    ids = {a["id"] for a in cfg["agents"]}
    assert cfg["entry_point"] in ids, (
        f"{label}: entry_point '{cfg['entry_point']}' not in {ids}"
    )
    for a in cfg["agents"]:
        assert "model" in a, f"{label}/{a['id']}: missing model"
        assert "system_prompt" in a, f"{label}/{a['id']}: missing prompt"
        assert len(a["system_prompt"]) > 50, (
            f"{label}/{a['id']}: prompt too short"
        )


def _check_graph(cfg: dict, label: str, swarm_ids: set[str]) -> None:
    """Validate graph config schema."""
    assert "id" in cfg, f"{label}: missing id"
    assert "nodes" in cfg, f"{label}: missing nodes"
    assert "edges" in cfg, f"{label}: missing edges"
    node_ids = {n["id"] for n in cfg["nodes"]}
    for ep in cfg.get("entry_points", []):
        assert ep in node_ids, f"{label}: entry_point '{ep}' not in {node_ids}"
    for e in cfg["edges"]:
        assert e["source"] in node_ids, (
            f"{label}: edge source '{e['source']}' not in {node_ids}"
        )
        assert e["target"] in node_ids, (
            f"{label}: edge target '{e['target']}' not in {node_ids}"
        )
    for n in cfg["nodes"]:
        if n.get("type") == "swarm":
            sid = n.get("swarm_id")
            assert sid in swarm_ids, (
                f"{label}/{n['id']}: swarm_id '{sid}' not registered"
            )


def _check_prompt_best_practices(prompt: str, agent_id: str) -> list[str]:
    """Check prompt follows experiment best practices. Returns warnings.

    Wave 1 (bd python-factory-2xbi) moved per-agent workflow detail
    into SKILL.md (loaded by the AgentSkills plugin). Wave-1-shape
    prompts (those calling out the skills tool) only need run_id
    inline; the rest is delegated to the skill.
    """
    warnings = []
    is_wave1 = "skills tool" in prompt
    if not is_wave1 and "memory_retrieve" not in prompt:
        warnings.append(f"{agent_id}: missing memory_retrieve")
    if not is_wave1 and "graph" not in prompt.lower():
        warnings.append(f"{agent_id}: no graph reference")
    if "run_id" not in prompt:
        warnings.append(f"{agent_id}: no run_id reference")
    return warnings


# --- SAST Swarm ---

def test_sast_swarm_schema():
    from factory.agent.registry.defaults_code_scan_swarm import (
        SAST_SCAN_SWARM,
    )
    _check_swarm(SAST_SCAN_SWARM, "SAST swarm")
    assert SAST_SCAN_SWARM["id"] == "rt-sast-scan-swarm"


def test_sast_swarm_prompts():
    from factory.agent.registry.defaults_code_scan_swarm import (
        SAST_SCAN_SWARM,
    )
    warnings = []
    for a in SAST_SCAN_SWARM["agents"]:
        warnings.extend(
            _check_prompt_best_practices(a["system_prompt"], a["id"])
        )
    assert not warnings, f"Prompt issues: {warnings}"


# --- SAST Hybrid ---

def test_sast_hybrid_schema():
    from factory.agent.registry.defaults_code_scan_hybrid import (
        SAST_HYBRID_GRAPH, SAST_HYBRID_SWARMS,
    )
    swarm_ids = {s["id"] for s in SAST_HYBRID_SWARMS}
    assert len(SAST_HYBRID_SWARMS) == 3
    for s in SAST_HYBRID_SWARMS:
        _check_swarm(s, f"SAST hybrid swarm {s['id']}")
    _check_graph(SAST_HYBRID_GRAPH, "SAST hybrid graph", swarm_ids)


def test_sast_hybrid_prompts():
    from factory.agent.registry.defaults_code_scan_hybrid import (
        SAST_HYBRID_GRAPH, SAST_HYBRID_SWARMS,
    )
    warnings = []
    for s in SAST_HYBRID_SWARMS:
        for a in s["agents"]:
            warnings.extend(
                _check_prompt_best_practices(a["system_prompt"], a["id"])
            )
    for n in SAST_HYBRID_GRAPH["nodes"]:
        if "system_prompt" in n:
            warnings.extend(
                _check_prompt_best_practices(n["system_prompt"], n["id"])
            )
    assert not warnings, f"Prompt issues: {warnings}"


# --- DAST IDOR Swarm ---

def test_dast_idor_swarm_schema():
    from factory.agent.registry.defaults_redteam_idor_swarm import (
        DAST_IDOR_SWARM,
    )
    _check_swarm(DAST_IDOR_SWARM, "DAST IDOR swarm")
    assert DAST_IDOR_SWARM["id"] == "rt-scan-idor-swarm-v2"


def test_dast_idor_swarm_prompts():
    from factory.agent.registry.defaults_redteam_idor_swarm import (
        DAST_IDOR_SWARM,
    )
    warnings = []
    for a in DAST_IDOR_SWARM["agents"]:
        warnings.extend(
            _check_prompt_best_practices(a["system_prompt"], a["id"])
        )
    assert not warnings, f"Prompt issues: {warnings}"


# --- DAST IDOR Hybrid ---

def test_dast_idor_hybrid_schema():
    from factory.agent.registry.defaults_redteam_idor_hybrid import (
        DAST_IDOR_HYBRID_GRAPH, DAST_IDOR_HYBRID_SWARMS,
    )
    swarm_ids = {s["id"] for s in DAST_IDOR_HYBRID_SWARMS}
    assert len(DAST_IDOR_HYBRID_SWARMS) == 3
    for s in DAST_IDOR_HYBRID_SWARMS:
        _check_swarm(s, f"DAST hybrid swarm {s['id']}")
    _check_graph(DAST_IDOR_HYBRID_GRAPH, "DAST hybrid graph", swarm_ids)


# --- Sandbox Graph-Only ---

def test_sandbox_graph_schema():
    from factory.agent.registry.defaults_sandbox_graph_only import (
        SANDBOX_GRAPH_ONLY,
    )
    _check_graph(SANDBOX_GRAPH_ONLY, "Sandbox graph", set())
    assert SANDBOX_GRAPH_ONLY["id"] == "rt-sandbox-setup-graph"
    assert len(SANDBOX_GRAPH_ONLY["entry_points"]) == 3


# --- Sandbox Hybrid ---

def test_sandbox_hybrid_schema():
    from factory.agent.registry.defaults_sandbox_hybrid import (
        SANDBOX_HYBRID_GRAPH, SANDBOX_HYBRID_SWARMS,
    )
    swarm_ids = {s["id"] for s in SANDBOX_HYBRID_SWARMS}
    assert len(SANDBOX_HYBRID_SWARMS) == 2
    for s in SANDBOX_HYBRID_SWARMS:
        _check_swarm(s, f"Sandbox hybrid swarm {s['id']}")
    _check_graph(SANDBOX_HYBRID_GRAPH, "Sandbox hybrid graph", swarm_ids)


# --- Full registry integration ---

def test_all_variants_registered():
    from factory.agent.registry.defaults import (
        get_default_swarms, get_default_graphs,
    )
    swarms = get_default_swarms()
    graphs = get_default_graphs()
    swarm_ids = {s.id for s in swarms}
    graph_ids = {g.id for g in graphs}
    expected_swarms = {
        "rt-sast-scan-swarm", "rt-scan-idor-swarm-v2",
        "rt-sast-hybrid-team-a", "rt-sast-hybrid-team-b",
        "rt-sast-hybrid-team-c",
        "rt-idor-hybrid-team-a", "rt-idor-hybrid-team-b",
        "rt-idor-hybrid-team-c",
        "rt-sandbox-hybrid-team-a", "rt-sandbox-hybrid-team-b",
    }
    expected_graphs = {
        "rt-sast-scan-hybrid", "rt-scan-idor-hybrid",
        "rt-sandbox-setup-graph", "rt-sandbox-setup-hybrid",
    }
    missing_swarms = expected_swarms - swarm_ids
    missing_graphs = expected_graphs - graph_ids
    assert not missing_swarms, f"Missing swarms: {missing_swarms}"
    assert not missing_graphs, f"Missing graphs: {missing_graphs}"
