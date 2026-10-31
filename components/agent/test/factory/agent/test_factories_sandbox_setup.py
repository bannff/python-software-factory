"""Tests for the sandbox-setup factory (bd python-factory-m4cp).

Mirrors ``test_factories_recon.py`` for the recon migration, adapted
to the sandbox-setup shape: 5 tasks (resource-creator → mock-applier
→ sandbox-validator → sandbox-summary → eval-scorer), pure-constant
factory (no per-call inputs), eval-tail embedded as ``eval-scorer``.

Pre-condition (i) of the meta-architect verdict (mem 33b12ebb): the
factory must be pure-deterministic — Hypothesis pins idempotency.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.agent.registry.defaults_sandbox_graph import (
    SANDBOX_SETUP_REGISTRATION,
    build_sandbox_setup_tasks,
)
from factory.agent.registry.factories import (
    FACTORY_REGISTRY,
    get_factory,
    known_factories,
)


# --- Schema / shape ----------------------------------------------------

def test_sandbox_setup_renders_5_tasks() -> None:
    """build_sandbox_setup_tasks returns the canonical 5-task DAG."""
    tasks = build_sandbox_setup_tasks()
    assert len(tasks) == 5
    assert [t["task_id"] for t in tasks] == [
        "resource-creator", "mock-applier", "sandbox-validator",
        "sandbox-summary", "eval-scorer",
    ]


def test_sandbox_setup_has_required_fields() -> None:
    """Every task carries strands_tools.workflow expected fields."""
    tasks = build_sandbox_setup_tasks()
    for t in tasks:
        for field in (
            "task_id", "description", "system_prompt",
            "tools", "model_provider", "model_settings",
            "dependencies", "priority", "timeout",
        ):
            assert field in t, f"{t['task_id']}: missing {field}"
        assert t["model_provider"] == "bedrock"
        assert "model_id" in t["model_settings"]
        assert isinstance(t["tools"], list) and t["tools"]


def test_sandbox_setup_tools_are_bare_names() -> None:
    """All tool names are bare — no dot-prefixed (workflow.py L329-336)."""
    tasks = build_sandbox_setup_tasks()
    for t in tasks:
        for tn in t["tools"]:
            assert "." not in tn, (
                f"{t['task_id']}: tool '{tn}' must be bare name"
            )


def test_sandbox_setup_no_unresolved_template_vars_owned_by_factory() -> None:
    """Factory pre-renders nothing — sandbox-setup takes no context."""
    tasks = build_sandbox_setup_tasks()
    creator = tasks[0]["system_prompt"]
    assert "{{run_id}}" in creator and "{{target_app}}" in creator


def test_sandbox_setup_dependencies_form_valid_dag() -> None:
    """Topological sort drains all 5 tasks."""
    tasks = build_sandbox_setup_tasks()
    ids = {t["task_id"] for t in tasks}
    for t in tasks:
        for dep in t["dependencies"]:
            assert dep in ids, f"{t['task_id']}: bad dep {dep}"
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


def test_sandbox_setup_has_pause_boundary_before_eval() -> None:
    """eval-scorer.dependencies == ['sandbox-summary'] — pause boundary."""
    tasks = build_sandbox_setup_tasks()
    by_id = {t["task_id"]: t for t in tasks}
    assert by_id["eval-scorer"]["dependencies"] == ["sandbox-summary"]


# --- Hypothesis property: pure-determinism ----------------------------

@settings(max_examples=50, deadline=None)
@given(
    run_id=st.text(min_size=1, max_size=20),
    target_app=st.text(min_size=1, max_size=20),
)
def test_sandbox_setup_factory_is_pure_over_any_context(
    run_id: str, target_app: str,
) -> None:
    """Sandbox-setup factory reads NO context — output identical."""
    factory = get_factory("sandbox_setup")
    a = factory({"run_id": run_id, "target_app": target_app})
    b = factory({"run_id": "different", "target_app": "other"})
    assert a == b, "sandbox-setup factory leaked context vars"# --- Registry surface --------------------------------------------------

def test_factory_registry_resolves_sandbox_setup() -> None:
    """The registration's factory key is in FACTORY_REGISTRY."""
    key = SANDBOX_SETUP_REGISTRATION.factory
    assert key in FACTORY_REGISTRY
    factory = get_factory(key)
    tasks = factory({"run_id": "r1", "target_app": "webgoat"})
    assert len(tasks) == 5


def test_known_factories_includes_sandbox_setup() -> None:
    """Discovery surface for tooling."""
    assert "sandbox_setup" in known_factories()


# --- Registration shape -----------------------------------------------

def test_sandbox_setup_registration_carries_string_factory_key() -> None:
    """Pre-condition (ii): factory is string registry key, not callable."""
    assert isinstance(SANDBOX_SETUP_REGISTRATION.factory, str)
    assert SANDBOX_SETUP_REGISTRATION.factory == "sandbox_setup"


def test_sandbox_setup_registration_id_for_alias_resolution() -> None:
    """sandbox-setup id stays for back-compat with agent_invoke_graph."""
    assert SANDBOX_SETUP_REGISTRATION.id == "sandbox-setup"
    assert SANDBOX_SETUP_REGISTRATION.kind == "workflow"


def test_sandbox_setup_registration_required_bricks() -> None:
    """Required bricks per design plan."""
    assert set(SANDBOX_SETUP_REGISTRATION.required_bricks) == {
        "sandbox", "graph", "memory", "evals", "metrics",
    }


def test_sandbox_setup_registration_context_vars() -> None:
    """Sandbox-setup takes only run_id + target_app per design plan."""
    assert set(SANDBOX_SETUP_REGISTRATION.context_vars) == {
        "run_id", "target_app",
    }


# --- Skill activation in factory-rendered prompts ---------------------
# Replaces 3 ``_SG`` ``PROMPT_CASES`` from ``test_default_prompts_skills``.

SANDBOX_PROMPT_CASES: list[tuple[int, str, str]] = [
    (0, "sandbox-ops", "sandbox setup creator"),
    (1, "sandbox-ops", "sandbox mock-applier"),
    (2, "sandbox-ops", "sandbox validator"),
    (3, "sandbox-ops", "sandbox summary"),
]


@pytest.mark.parametrize(
    "idx, expected_skill, expected_role",
    SANDBOX_PROMPT_CASES,
    ids=[f"sandbox[{i}]" for i, _, _ in SANDBOX_PROMPT_CASES],
)
def test_sandbox_factory_prompt_is_thin_and_skill_aware(
    idx: int, expected_skill: str, expected_role: str,
) -> None:
    """build_sandbox_setup_tasks()[i].system_prompt mirrors SKILL.md shape."""
    tasks = build_sandbox_setup_tasks()
    prompt = tasks[idx]["system_prompt"]
    assert isinstance(prompt, str)
    assert len(prompt) < 1500, f"sandbox[{idx}] is {len(prompt)} chars"
    assert expected_skill in prompt
    assert "skills tool" in prompt
    assert expected_role in prompt
