"""Tests for the open-scope DAST factory (bd python-factory-vy9r).

Sibling of ``test_factories_sast_open.py`` adapted to the flat
3-parallel topology — no DAG dependencies between testers. Open
DAST takes no per-call inputs (no vuln_class), so the Hypothesis
property pins idempotency over arbitrary contexts.

Pre-conditions: (i) factory pure-deterministic, (ii) string factory
key (Option A), (iii) no ``{{vuln_class}}`` template, (iv) skills
use dast-open-scan (not IDOR wedge), (v) bare-name tools.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from hypothesis import given, settings, strategies as st

from factory.agent.registry.defaults_dast_open import (
    DAST_OPEN_REGISTRATION, build_dast_open_tasks,
)
from factory.agent.registry.factories import (
    FACTORY_REGISTRY, get_factory, known_factories,
)


def test_dast_open_renders_3_tasks() -> None:
    tasks = build_dast_open_tasks()
    assert len(tasks) == 3
    assert [t["task_id"] for t in tasks] == [
        "gptoss-dast", "sonnet-dast", "glm5-dast",
    ]


def test_dast_open_has_required_fields() -> None:
    """Every task carries strands_tools.workflow expected fields."""
    for t in build_dast_open_tasks():
        for field in (
            "task_id", "description", "system_prompt", "tools",
            "model_provider", "model_settings", "dependencies",
            "priority", "timeout",
        ):
            assert field in t, f"{t['task_id']}: missing {field}"
        assert t["model_provider"] == "bedrock"
        assert "model_id" in t["model_settings"]
        assert isinstance(t["tools"], list) and t["tools"]


def test_dast_open_tools_are_bare_names() -> None:
    """All tool names are bare — workflow.py L329-336 filter contract."""
    for t in build_dast_open_tasks():
        for tn in t["tools"]:
            assert "." not in tn, f"{t['task_id']}: '{tn}' must be bare"


def test_dast_open_no_vuln_class_in_prompts() -> None:
    """Pre-condition (iii): regression guard against per-class leak."""
    for t in build_dast_open_tasks():
        assert "{{vuln_class}}" not in t["system_prompt"]
        assert "{{vuln_class}}" not in t["description"]


def test_dast_open_skill_refs_use_dast_open_scan() -> None:
    """Pre-condition (iv): NO IDOR-wedge skills (regression guard)."""
    for t in build_dast_open_tasks():
        prompt = t["system_prompt"]
        assert "dast-open-scan" in prompt, f"{t['task_id']}: missing"
        assert "idor-testing" not in prompt, f"{t['task_id']}: leaked wedge"


def test_dast_open_dependencies_are_empty_for_parallel_scanners() -> None:
    """All 3 testers run flat-parallel: dependencies=[] for each."""
    for t in build_dast_open_tasks():
        assert t["dependencies"] == [], f"{t['task_id']}: deps not flat"


@settings(max_examples=50, deadline=None)
@given(
    target_app=st.text(min_size=1, max_size=20),
    run_id=st.text(min_size=1, max_size=20),
    target_url=st.text(min_size=1, max_size=20),
    sandbox_env_id=st.text(min_size=1, max_size=20),
    sast_run_id=st.text(min_size=1, max_size=20),
)
def test_dast_open_factory_is_pure_over_any_context(
    target_app: str, run_id: str, target_url: str,
    sandbox_env_id: str, sast_run_id: str,
) -> None:
    """Pre-condition (i): dast_open factory reads NO context."""
    factory = get_factory("dast_open")
    a = factory({
        "target_app": target_app, "run_id": run_id,
        "target_url": target_url, "sandbox_env_id": sandbox_env_id,
        "sast_run_id": sast_run_id,
    })
    b = factory({
        "target_app": "x", "run_id": "x", "target_url": "x",
        "sandbox_env_id": "x", "sast_run_id": "x",
    })
    assert a == b, "dast_open factory leaked context vars"


def test_factory_registry_resolves_dast_open() -> None:
    key = DAST_OPEN_REGISTRATION.factory
    assert key in FACTORY_REGISTRY
    tasks = get_factory(key)({"target_app": "webgoat", "run_id": "r1"})
    assert len(tasks) == 3


def test_known_factories_includes_dast_open() -> None:
    assert "dast_open" in known_factories()


def test_dast_open_registration_carries_string_factory_key() -> None:
    """Pre-condition (ii): factory is string key, not callable."""
    assert isinstance(DAST_OPEN_REGISTRATION.factory, str)
    assert DAST_OPEN_REGISTRATION.factory == "dast_open"


def test_dast_open_registration_id_is_dast() -> None:
    assert DAST_OPEN_REGISTRATION.id == "dast"


def test_dast_open_registration_kind_is_workflow() -> None:
    assert DAST_OPEN_REGISTRATION.kind == "workflow"


def test_dast_open_registration_required_bricks() -> None:
    """Required bricks include sandbox (HTTP probing + AWS CLI)."""
    assert set(DAST_OPEN_REGISTRATION.required_bricks) == {
        "graph", "security", "memory", "kb", "sandbox",
    }
    assert "sandbox" in DAST_OPEN_REGISTRATION.required_bricks


def test_dast_open_registration_context_vars_excludes_vuln_class() -> None:
    assert "vuln_class" not in DAST_OPEN_REGISTRATION.context_vars
    assert set(DAST_OPEN_REGISTRATION.context_vars) == {
        "target_app", "run_id", "target_url",
        "sandbox_env_id", "sast_run_id",
    }


# --- QA-tester additions (verify phase, bd python-factory-vy9r) ------

def test_dast_open_required_bricks_in_brick_inventory() -> None:
    """required_bricks resolve to a real components/<brick>/BRICK.yaml."""
    repo_root = Path(__file__).resolve().parents[5]
    components = repo_root / "components"
    for brick in DAST_OPEN_REGISTRATION.required_bricks:
        assert (components / brick / "BRICK.yaml").is_file(), (
            f"required_brick {brick!r} missing"
        )


def test_dast_open_factory_returns_fresh_lists_each_call() -> None:
    """Factory MUST NOT alias mutable state across calls."""
    factory = get_factory("dast_open")
    a = factory({"target_app": "x", "run_id": "r"})
    a.append({"task_id": "rogue", "system_prompt": "x"})
    a[0]["task_id"] = "MUTATED"
    b = factory({"target_app": "x", "run_id": "r"})
    assert b[0]["task_id"] == "gptoss-dast"
    assert all(t.get("task_id") != "rogue" for t in b)
    assert len(b) == 3


def test_dast_open_factory_concurrent_invocation_safety() -> None:
    """8 threads invoking the factory MUST produce identical results.
    Mirrors test_factories_sandbox_setup_qa.test_factory_concurrent_*."""
    factory = get_factory("dast_open")
    results: list[list[dict]] = []
    lock = threading.Lock()

    def call() -> None:
        out = factory({"run_id": "t", "target_app": "x"})
        with lock:
            results.append(out)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 8
    canonical = results[0]
    for i, r in enumerate(results[1:], start=1):
        assert r == canonical, f"Thread {i} divergent — race condition"


def test_dast_open_prompt_mentions_attack_chaining() -> None:
    """Tester prompts include cross-class chaining language —
    user explicitly stated open variants must surface chains."""
    chain_re = re.compile(r"chain|compound|across", re.IGNORECASE)
    for t in build_dast_open_tasks():
        assert chain_re.search(t["system_prompt"]), (
            f"{t['task_id']}: missing cross-class language"
        )
