"""Regression coverage for framework-neutral evaluator paths."""
from __future__ import annotations

import pytest

from factory.evals.runtime.adapters import evaluator_adapter, evaluator_factory
from factory.evals.runtime.adapters import session_evaluator


def _session() -> dict:
    return {"session_id": "session", "traces": [{"trace_id": "trace", "spans": [{"name": "agent"}]}]}


@pytest.mark.parametrize("names", [[], ["unknown"], ["output", "unknown"], ["output", "output"]])
def test_factory_rejects_invalid_alias_lists_atomically(names) -> None:
    with pytest.raises(ValueError):
        evaluator_factory.build_evaluators(names)
    with pytest.raises(ValueError):
        evaluator_factory.needs_trace(names)


def test_factory_builds_one_sdk_judge_per_alias() -> None:
    names = list(evaluator_factory.EVALUATOR_REGISTRY)
    evaluators = evaluator_factory.build_evaluators(names)
    assert len(evaluators) == len(names)
    assert [
        evaluator_factory.alias_for_evaluator(ev, framework="strands")
        for ev in evaluators
    ] == names
    assert not evaluator_factory.needs_trace(["output"])
    assert evaluator_factory.needs_trace(["helpfulness"])


def test_deterministic_default_rejects_llm_judge_alias() -> None:
    with pytest.raises(ValueError, match="deterministic provider does not support"):
        evaluator_adapter.evaluate_output("in", "out", "helpfulness")


@pytest.mark.parametrize("kwargs", [{}, {"session_data": {}}, {"otel_spans_json": []}])
def test_session_evaluation_rejects_absent_or_empty_evidence(kwargs) -> None:
    with pytest.raises(ValueError):
        session_evaluator.evaluate_with_real_session(
            "input", "output", ["output"], **kwargs,
        )


def test_serialized_nonempty_session_evidence_is_accepted() -> None:
    assert session_evaluator._build_session(session_data=_session()) == _session()


def test_session_evaluation_aggregates_on_the_rail(monkeypatch) -> None:
    from factory.evals.runtime.adapters.evaluator_factory import EvaluationOutput

    class _FakeEval:
        def __init__(self, name: str) -> None:
            self.name = name

        def evaluate(self, _data):
            return [EvaluationOutput(1.0, True, "ok", "pass")]

    class _FakeProvider:
        framework = "strands"

        def build(self, names, rubric=""):
            return [_FakeEval(name) for name in names]

    monkeypatch.setattr(
        session_evaluator, "get_provider", lambda _fw: _FakeProvider(),
    )
    result = session_evaluator.evaluate_with_real_session(
        "input", "output", ["output", "helpfulness"], session=_session(),
    )
    assert [row["score"] for row in result["results"]] == [1.0, 1.0]
    assert result["summary"]["aggregation_policy"] == "all_requested"
