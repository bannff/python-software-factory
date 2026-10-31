"""Focused tests for Evals persistence port composition and injection."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from factory.evals.runtime.adapters.custom_adapter import CustomEvalRunner
from factory.evals.runtime.adapters.persistence import NoOpEvalPersistence
from factory.evals.runtime.adapters.sop_adapter import SOPState, _materialize_eval_run
from factory.evals.runtime.ports import EvalCase, EvalMetrics, EvalRun, EvalSuite
from factory.evals.runtime.runtime import EvalsRuntime


@dataclass
class RecordingPersistence:
    suites: list[EvalSuite] = field(default_factory=list)
    runs: list[tuple[EvalRun, EvalMetrics]] = field(default_factory=list)

    def persist_suite(self, suite: EvalSuite) -> None:
        self.suites.append(suite)

    def persist_run(self, run: EvalRun, metrics: EvalMetrics) -> None:
        self.runs.append((run, metrics))


def _suite() -> EvalSuite:
    return EvalSuite(
        id="suite", name="suite",
        cases=[EvalCase(id="case", name="case", input={"x": 1}, expected={"x": 1})],
    )


def test_custom_runner_defaults_to_noop_persistence() -> None:
    runner = CustomEvalRunner()
    runner.create_suite(_suite())
    assert runner.run_suite("suite", lambda value: value).status == "completed"


def test_custom_runner_uses_injected_persistence() -> None:
    persistence = RecordingPersistence()
    runner = CustomEvalRunner(persistence=persistence)
    runner.create_suite(_suite())
    run = runner.run_suite("suite", lambda value: value)
    assert persistence.suites[0].id == "suite"
    assert persistence.runs[0][0] is run


def test_runtime_composes_noop_unless_graph_is_explicit() -> None:
    assert isinstance(EvalsRuntime()._persistence, NoOpEvalPersistence)
    assert EvalsRuntime({"persistence": "graph"})._persistence.__class__.__name__ == "GraphEvalsStore"


def test_sop_materialization_uses_injected_persistence() -> None:
    persistence = RecordingPersistence()
    state = SOPState(
        id="sop", agent_description="agent", test_cases=[{"id": "case"}],
        eval_results={"summary": {"pass_rate": 1.0, "avg_score": 0.8}},
    )
    _materialize_eval_run(state, persistence)
    assert persistence.suites[0].id == "sop-suite-sop"
    assert persistence.runs[0][1].total_cases == 1


class FailingPersistence:
    def persist_suite(self, suite: EvalSuite) -> None:
        raise RuntimeError("persistence failed")

    def persist_run(self, run: EvalRun, metrics: EvalMetrics) -> None:
        raise RuntimeError("persistence failed")


def test_custom_runner_propagates_persistence_errors() -> None:
    runner = CustomEvalRunner(persistence=FailingPersistence())
    with pytest.raises(RuntimeError, match="persistence failed"):
        runner.create_suite(_suite())
