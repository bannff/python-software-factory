"""Edge-case Hypothesis property tests for factory registry.

Sister file: ``test_factories.py`` (implementer-authored, covers
shape/idempotency/registry surface). This file pins behavior on
inputs the implementer's tests don't fuzz:
  - very-long ``target_app`` strings (no buffer-shape leak into tasks)
  - unicode ``vuln_class`` values (factory does NOT raise — pre-render
    happens here; downstream ``launch_validator`` is the gate that
    refuses unknown skills before the workflow starts)
  - concurrent factory invocation (pure function, no module-level
    state mutation across threads)

Filed under bd python-factory-a4h7. Pre-condition (i) of the
meta-architect verdict — factory must be pure-deterministic — is
asserted from a different angle here than in the sister file.
"""
from __future__ import annotations

import threading

from hypothesis import given, settings, strategies as st

from factory.agent.registry.defaults_code_scan import (
    build_sast_targeted_tasks,
)
from factory.agent.registry.factories import get_factory
from factory.agent.registry.vuln_class_config import VULN_CLASS_CONFIG

_VULN_CLASSES = list(VULN_CLASS_CONFIG.keys())


# --- Long target_app (template payload doesn't crash factory) --------

@settings(max_examples=50, deadline=None)
@given(
    vuln_class=st.sampled_from(_VULN_CLASSES),
    target_app=st.text(min_size=200, max_size=2000),
)
def test_factory_handles_very_long_target_app(
    vuln_class: str, target_app: str,
) -> None:
    """Factory takes context dict; ``target_app`` is left as
    template marker (resolved later by WorkflowExecutor). Even
    very long values must not crash the factory or change the
    structural shape (6 tasks, identical task_ids)."""
    factory = get_factory("sast_targeted")
    tasks = factory({"vuln_class": vuln_class, "target_app": target_app})
    assert len(tasks) == 6
    assert [t["task_id"] for t in tasks] == [
        "gptoss-sast", "sonnet-sast", "glm5-sast",
        "hierarchy-analyzer", "consolidator", "validator",
    ]
    # ``{{target_app}}`` must STILL be a template marker — factory
    # only renders ``{{vuln_class}}`` and ``{{agent_id}}``.
    for t in tasks:
        assert "{{target_app}}" in t["system_prompt"], (
            f"{t['task_id']}: target_app got pre-rendered (factory leak)"
        )


# --- Unicode vuln_class (pre-render happens; validator gates) --------

@settings(max_examples=30, deadline=None)
@given(
    vuln_class=st.text(
        min_size=1, max_size=30,
        # Letters, digits, marks — covers ASCII + non-Latin scripts.
        alphabet=st.characters(whitelist_categories=("L", "N", "M")),
    ),
)
def test_factory_pre_renders_unicode_vuln_class(vuln_class: str) -> None:
    """Factory MUST pre-render whatever ``vuln_class`` it gets — the
    structural property holds. The skill-existence gate is the
    launch_validator's job, not the factory's. This pins the
    boundary contract: factory is pure rendering, validator is
    semantic gate."""
    tasks = build_sast_targeted_tasks(vuln_class)
    assert len(tasks) == 6
    # vuln_class is rendered into the system_prompt for SAST tasks;
    # the un-rendered template MUST NOT survive into the prompt.
    for t in tasks:
        assert "{{vuln_class}}" not in t["system_prompt"], (
            f"{t['task_id']}: factory left vuln_class template var"
        )
        # And the rendered value really is the input.
        # (validator/consolidator/hierarchy-analyzer all reference
        # vuln_class in their prompts.)
        assert vuln_class in t["system_prompt"]


# --- Concurrent factory invocation -----------------------------------

@settings(max_examples=20, deadline=None)
@given(
    vuln_classes=st.lists(
        st.sampled_from(_VULN_CLASSES), min_size=4, max_size=12,
    ),
)
def test_factory_is_threadsafe(vuln_classes: list[str]) -> None:
    """Factory is pure — concurrent calls from many threads must
    produce the same task list per ``vuln_class`` as a serial call."""
    factory = get_factory("sast_targeted")
    serial = {vc: factory({"vuln_class": vc}) for vc in set(vuln_classes)}

    results: dict[int, list[dict]] = {}
    lock = threading.Lock()

    def call(idx: int, vc: str) -> None:
        out = factory({"vuln_class": vc})
        with lock:
            results[idx] = out

    threads = [
        threading.Thread(target=call, args=(i, vc))
        for i, vc in enumerate(vuln_classes)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, vc in enumerate(vuln_classes):
        assert results[i] == serial[vc], (
            f"concurrent call {i} ({vc}) drifted from serial baseline"
        )
