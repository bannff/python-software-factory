"""Tests for the open-scope SAST factory (bd python-factory-c3hx).

Sibling of ``test_factories_recon.py`` — open SAST factory takes
no per-call inputs (no vuln_class), so the Hypothesis property
pins idempotency over arbitrary contexts.

Pre-conditions: (i) factory pure-deterministic, (ii) string factory
key (Option A), (iii) no ``{{vuln_class}}`` template, (iv) skills
use sast-open-scan (not IDOR wedge), (v) bare-name tools.
"""
from __future__ import annotations

import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

from factory.agent.registry.defaults_sast_open import (
    SAST_OPEN_REGISTRATION, build_sast_open_tasks,
)
from factory.agent.registry.factories import (
    FACTORY_REGISTRY, get_factory, known_factories,
)


def test_sast_open_renders_6_tasks() -> None:
    tasks = build_sast_open_tasks()
    assert len(tasks) == 6
    assert [t["task_id"] for t in tasks] == [
        "gptoss-sast", "sonnet-sast", "glm5-sast",
        "hierarchy-analyzer", "consolidator", "validator",
    ]


def test_sast_open_has_required_fields() -> None:
    """Every task carries strands_tools.workflow expected fields."""
    for t in build_sast_open_tasks():
        for field in (
            "task_id", "description", "system_prompt", "tools",
            "model_provider", "model_settings", "dependencies",
            "priority", "timeout",
        ):
            assert field in t, f"{t['task_id']}: missing {field}"
        assert t["model_provider"] == "bedrock"
        assert "model_id" in t["model_settings"]
        assert isinstance(t["tools"], list) and t["tools"]


def test_sast_open_tools_are_bare_names() -> None:
    """All tool names are bare — workflow.py L329-336 filter contract."""
    for t in build_sast_open_tasks():
        for tn in t["tools"]:
            assert "." not in tn, f"{t['task_id']}: '{tn}' must be bare"


def test_sast_open_no_vuln_class_in_prompts() -> None:
    """Pre-condition (iii): regression guard against per-class leak."""
    for t in build_sast_open_tasks():
        assert "{{vuln_class}}" not in t["system_prompt"]
        assert "{{vuln_class}}" not in t["description"]


def test_sast_open_skill_refs_use_sast_open_scan() -> None:
    """Pre-condition (iv): NO IDOR-wedge skills (regression guard)."""
    by_id = {t["task_id"]: t for t in build_sast_open_tasks()}
    for tid in ("gptoss-sast", "sonnet-sast", "glm5-sast", "validator"):
        prompt = by_id[tid]["system_prompt"]
        assert "sast-open-scan" in prompt, f"{tid}: missing sast-open-scan"
        assert "idor-code-scan" not in prompt, f"{tid}: leaked IDOR wedge"
        assert "{{vuln_class}}-code-scan" not in prompt
        assert "<vuln_class>-code-scan" not in prompt


def test_sast_open_dependencies_form_valid_dag() -> None:
    """Topological sort drains all 6 tasks (no cycles)."""
    tasks = build_sast_open_tasks()
    ids = {t["task_id"] for t in tasks}
    for t in tasks:
        for dep in t["dependencies"]:
            assert dep in ids
    indeg = {t["task_id"]: len(t["dependencies"]) for t in tasks}
    by_dep = {t["task_id"]: list(t["dependencies"]) for t in tasks}
    queue = [tid for tid, n in indeg.items() if n == 0]
    drained = 0
    while queue:
        tid = queue.pop(0)
        drained += 1
        for other, deps in by_dep.items():
            if tid in deps:
                deps.remove(tid)
                indeg[other] -= 1
                if indeg[other] == 0:
                    queue.append(other)
    assert drained == len(tasks), "DAG has a cycle"


def test_sast_open_prompt_mentions_attack_chaining() -> None:
    """Scanner prompts include cross-class chaining language."""
    by_id = {t["task_id"]: t for t in build_sast_open_tasks()}
    chain_re = re.compile(r"chain|compound|across", re.IGNORECASE)
    for tid in ("gptoss-sast", "sonnet-sast", "glm5-sast"):
        assert chain_re.search(by_id[tid]["system_prompt"])


@settings(max_examples=50, deadline=None)
@given(
    target_app=st.text(min_size=1, max_size=20),
    run_id=st.text(min_size=1, max_size=20),
    target_packages=st.text(min_size=1, max_size=20),
    sast_workspace=st.text(min_size=1, max_size=20),
)
def test_sast_open_factory_is_pure_over_any_context(
    target_app: str, run_id: str,
    target_packages: str, sast_workspace: str,
) -> None:
    """Pre-condition (i): sast_open factory reads NO context."""
    factory = get_factory("sast_open")
    a = factory({
        "target_app": target_app, "run_id": run_id,
        "target_packages": target_packages,
        "sast_workspace": sast_workspace,
    })
    b = factory({
        "target_app": "x", "run_id": "x",
        "target_packages": "x", "sast_workspace": "x",
    })
    assert a == b, "sast_open factory leaked context vars"


def test_factory_registry_resolves_sast_open() -> None:
    key = SAST_OPEN_REGISTRATION.factory
    assert key in FACTORY_REGISTRY
    tasks = get_factory(key)({"target_app": "webgoat", "run_id": "r1"})
    assert len(tasks) == 6


def test_known_factories_includes_sast_open() -> None:
    assert "sast_open" in known_factories()


def test_sast_open_registration_carries_string_factory_key() -> None:
    """Pre-condition (ii): factory is string key, not callable."""
    assert isinstance(SAST_OPEN_REGISTRATION.factory, str)
    assert SAST_OPEN_REGISTRATION.factory == "sast_open"


def test_sast_open_registration_id_is_sast() -> None:
    assert SAST_OPEN_REGISTRATION.id == "sast"


def test_sast_open_registration_kind_is_workflow() -> None:
    assert SAST_OPEN_REGISTRATION.kind == "workflow"


def test_sast_open_registration_required_bricks() -> None:
    assert set(SAST_OPEN_REGISTRATION.required_bricks) == {
        "graph", "security", "memory", "kb",
    }


def test_sast_open_registration_context_vars_excludes_vuln_class() -> None:
    assert "vuln_class" not in SAST_OPEN_REGISTRATION.context_vars
    assert set(SAST_OPEN_REGISTRATION.context_vars) == {
        "target_app", "run_id", "target_packages", "sast_workspace",
    }


# --- QA-tester additions (verify phase, bd python-factory-c3hx) ------

def test_sast_open_required_bricks_in_brick_inventory() -> None:
    """required_bricks resolve to a real components/<brick>/BRICK.yaml."""
    repo_root = Path(__file__).resolve().parents[5]
    components = repo_root / "components"
    for brick in SAST_OPEN_REGISTRATION.required_bricks:
        assert (components / brick / "BRICK.yaml").is_file(), (
            f"required_brick {brick!r} missing"
        )


def test_sast_open_validator_uses_open_skills() -> None:
    """Design (mem f4d01009): validator uses pentest-ops + sast-open-scan
    + swarm-collaboration (same stack as scanners)."""
    by_id = {t["task_id"]: t for t in build_sast_open_tasks()}
    prompt = by_id["validator"]["system_prompt"]
    for skill in ("pentest-ops", "sast-open-scan", "swarm-collaboration"):
        assert skill in prompt, f"validator: missing {skill}"


def test_sast_open_factory_returns_fresh_lists_each_call() -> None:
    """Factory MUST NOT alias mutable state across calls."""
    factory = get_factory("sast_open")
    a = factory({"target_app": "x", "run_id": "r"})
    a.append({"task_id": "rogue", "system_prompt": "x"})
    a[0]["task_id"] = "MUTATED"
    b = factory({"target_app": "x", "run_id": "r"})
    assert b[0]["task_id"] == "gptoss-sast"
    assert all(t.get("task_id") != "rogue" for t in b)
    assert len(b) == 6
