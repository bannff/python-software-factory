"""Tests for the factory registry (bd python-factory-a4h7).

Pre-condition (i) of the meta-architect verdict: the workflow
factory must be pure-deterministic across all 6 vuln_classes.
Hypothesis property test pins idempotency — two calls with the
same vuln_class produce identical task lists.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.agent.registry.defaults_code_scan import (
    SAST_TARGETED_REGISTRATION,
    build_sast_targeted_tasks,
)
from factory.agent.registry.factories import (
    FACTORY_REGISTRY,
    get_factory,
    known_factories,
)
from factory.agent.registry.vuln_class_config import VULN_CLASS_CONFIG

_VULN_CLASSES = list(VULN_CLASS_CONFIG.keys())


# --- Schema / shape ----------------------------------------------------

@pytest.mark.parametrize("vuln_class", _VULN_CLASSES)
def test_sast_targeted_renders_6_tasks_per_vuln_class(vuln_class: str) -> None:
    """All 6 supported vuln classes produce the canonical 6-task DAG."""
    tasks = build_sast_targeted_tasks(vuln_class)
    assert len(tasks) == 6, f"{vuln_class}: got {len(tasks)} tasks"
    ids = [t["task_id"] for t in tasks]
    assert ids == [
        "gptoss-sast", "sonnet-sast", "glm5-sast",
        "hierarchy-analyzer", "consolidator", "validator",
    ], ids


@pytest.mark.parametrize("vuln_class", _VULN_CLASSES)
def test_sast_targeted_has_required_fields(vuln_class: str) -> None:
    """Every task carries the fields strands_tools.workflow expects."""
    tasks = build_sast_targeted_tasks(vuln_class)
    for t in tasks:
        for field in (
            "task_id", "description", "system_prompt",
            "tools", "model_provider", "model_settings",
            "dependencies", "priority", "timeout",
        ):
            assert field in t, f"{vuln_class}/{t['task_id']}: missing {field}"
        assert t["model_provider"] == "bedrock"
        assert isinstance(t["tools"], list)
        for tn in t["tools"]:
            # BARE tool names — workflow.py L329-336 keys registry
            # by TOOL_SPEC.name. See bd python-factory-a4h7.
            assert "." not in tn, f"task tool '{tn}' must be bare name"


@pytest.mark.parametrize("vuln_class", _VULN_CLASSES)
def test_sast_targeted_no_unresolved_template_vars(vuln_class: str) -> None:
    """Factory pre-renders {{vuln_class}} and {{agent_id}}."""
    tasks = build_sast_targeted_tasks(vuln_class)
    for t in tasks:
        assert "{{vuln_class}}" not in t["description"]
        assert "{{vuln_class}}" not in t["system_prompt"]
        assert "{{agent_id}}" not in t["description"]


@pytest.mark.parametrize("vuln_class", _VULN_CLASSES)
def test_sast_targeted_dependencies_form_valid_dag(vuln_class: str) -> None:
    """Every dependency references a real task_id; no cycles."""
    tasks = build_sast_targeted_tasks(vuln_class)
    ids = {t["task_id"] for t in tasks}
    for t in tasks:
        for dep in t["dependencies"]:
            assert dep in ids, f"{t['task_id']}: bad dep {dep}"
    # Topological sort (Kahn's). Cycle-free if every task drains.
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


# --- Hypothesis property: idempotency ---------------------------------

@settings(max_examples=50, deadline=None)
@given(vuln_class=st.sampled_from(_VULN_CLASSES))
def test_factory_is_deterministic_over_vuln_class(vuln_class: str) -> None:
    """Same input → identical task list (pure-deterministic invariant)."""
    a = build_sast_targeted_tasks(vuln_class)
    b = build_sast_targeted_tasks(vuln_class)
    assert a == b, f"{vuln_class}: factory drift between calls"


# Independent fuzz: factory MUST stay pure even when called from the
# registry path with synthetic contexts (envelope vars beyond
# vuln_class don't leak into the task list since the factory only
# reads ``vuln_class``). 30+ examples per pre-condition (i).
@settings(max_examples=30, deadline=None)
@given(
    vuln_class=st.sampled_from(_VULN_CLASSES),
    target_app=st.text(min_size=1, max_size=20),
    run_id=st.text(min_size=1, max_size=20),
    target_packages=st.text(min_size=1, max_size=20),
)
def test_registry_factory_only_reads_vuln_class(
    vuln_class: str, target_app: str, run_id: str, target_packages: str,
) -> None:
    """Registry path: ``get_factory("sast_targeted")`` must produce
    the same task list regardless of unrelated context vars.
    Other context vars are template markers that get resolved later
    by the executor (``inject_variables`` over rendered prompts)."""
    factory = get_factory("sast_targeted")
    a = factory({
        "vuln_class": vuln_class, "target_app": target_app,
        "run_id": run_id, "target_packages": target_packages,
    })
    b = factory({
        "vuln_class": vuln_class, "target_app": "other",
        "run_id": "other", "target_packages": "other",
    })
    # Strip rendered fields whose templates depend on later vars, so
    # we can compare just the structural invariants the factory
    # owns: task ids, deps, model bindings, tools.
    def _shape(tasks: list[dict]) -> list[dict]:
        return [
            {"id": t["task_id"], "deps": t["dependencies"],
             "tools": t["tools"], "model": t["model_settings"]}
            for t in tasks
        ]
    assert _shape(a) == _shape(b), (
        f"{vuln_class}: factory shape leaked unrelated context vars"
    )


# --- Registry surface --------------------------------------------------

def test_factory_registry_resolves_sast_targeted() -> None:
    """The registration's factory key is in FACTORY_REGISTRY."""
    key = SAST_TARGETED_REGISTRATION.factory
    assert key in FACTORY_REGISTRY
    factory = get_factory(key)
    tasks = factory({"vuln_class": "idor"})
    assert len(tasks) == 6


def test_get_factory_unknown_raises_keyerror() -> None:
    """Unknown factory keys surface clearly to the caller."""
    with pytest.raises(KeyError) as ei:
        get_factory("not_a_real_factory_xyz")
    assert "not_a_real_factory_xyz" in str(ei.value)


def test_known_factories_includes_sast_targeted() -> None:
    """Discovery surface for tooling."""
    assert "sast_targeted" in known_factories()


# --- Registration shape -----------------------------------------------

def test_sast_targeted_registration_carries_string_factory_key() -> None:
    """Pre-condition (ii): factory is a string registry key, not callable."""
    assert isinstance(SAST_TARGETED_REGISTRATION.factory, str)
    assert SAST_TARGETED_REGISTRATION.factory == "sast_targeted"


def test_sast_targeted_registration_keeps_id_for_alias_resolution() -> None:
    """rt-sast-scan id stays so agent_invoke_graph(graph_id=...) works."""
    assert SAST_TARGETED_REGISTRATION.id == "rt-sast-scan"
    assert SAST_TARGETED_REGISTRATION.kind == "workflow"
