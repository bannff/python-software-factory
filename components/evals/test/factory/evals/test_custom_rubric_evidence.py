"""Regression: custom rubrics must reach the judge even without placeholders.

A bare rubric ("score 1.0 if X") previously judged blind because openevals
only injects params the prompt references — both good and bad outputs scored
0.0. The providers now inject an evidence block when the rubric omits it.
"""
from __future__ import annotations

import pytest

from factory.evals.runtime.adapters.evaluator_providers.langchain_provider import (
    _ensure_evidence,
)


def test_bare_rubric_gets_output_placeholder_injected():
    wrapped = _ensure_evidence("Score 1.0 only if the answer mentions slicing.")
    assert "{outputs}" in wrapped
    assert "{inputs}" in wrapped


def test_rubric_with_placeholder_is_left_untouched():
    rubric = "Judge this: {inputs} -> {outputs}"
    assert _ensure_evidence(rubric) == rubric


def test_injected_block_has_no_reference_placeholder():
    # reference_outputs is optional; an orphan placeholder KeyErrors in openevals
    # when no reference is supplied, so the auto-injected block must omit it.
    assert "{reference_outputs}" not in _ensure_evidence("bare rubric")


def test_trajectory_custom_injects_outputs_when_missing(monkeypatch):
    pytest.importorskip("agentevals.trajectory.llm")
    from factory.evals.runtime.adapters.evaluator_providers.langchain_trajectory import (
        LangChainTrajectoryProvider,
    )
    monkeypatch.setattr(
        "factory.evals.runtime.adapters.evaluator_providers.langchain_trajectory.get_judge_model",
        lambda: object(),
    )
    # Build a custom trajectory evaluator with a bare rubric; its prompt must
    # carry {outputs} so the trajectory reaches the judge (no Bedrock call here).
    ev = LangChainTrajectoryProvider().build(
        ["custom"], rubric="Score 1.0 if a weather tool was called.",
        options=None,
    )[0]
    assert "{outputs}" in ev._prompt
