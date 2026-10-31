"""Strands adapter for evals brick.

Integrates with the Strands Evals SDK (strands-agents-evals) to provide
LLM-as-a-Judge evaluators, experiment management, and agent execution.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable

from ..ports import (
    EvalCase, EvalResult, EvalSuite, EvalRun, EvalMetrics, EvalHealth,
    ExperimentConfig, ExperimentReport, EvalPersistencePort,
)
from .evaluator_catalog import get_available_evaluators
from .persistence import NoOpEvalPersistence

logger = logging.getLogger(__name__)


def _check_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


class StrandsEvalRunner:
    """Strands-based evaluation runner using strands-agents-evals SDK."""

    def __init__(
        self, persistence: EvalPersistencePort | None = None, **kwargs: Any,
    ) -> None:
        self._suites: dict[str, EvalSuite] = {}
        self._runs: dict[str, EvalRun] = {}
        self._experiments: dict[str, ExperimentReport] = {}
        self._persistence = (
            persistence if persistence is not None else NoOpEvalPersistence()
        )
        self._evals_available = _check_import("strands_evals")
        self._agents_available = _check_import("strands")

    # -- EvalRunner protocol (backward compat) --
    def create_suite(self, suite: EvalSuite) -> EvalSuite:
        self._suites[suite.id] = suite
        self._persistence.persist_suite(suite)
        return suite

    def get_suite(self, suite_id: str) -> EvalSuite | None:
        return self._suites.get(suite_id)

    def list_suites(self) -> list[EvalSuite]:
        return list(self._suites.values())

    def run_suite(
        self, suite_id: str,
        agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
        scorer_fn: Callable[[EvalCase, dict[str, Any]], EvalResult] | None = None,
    ) -> EvalRun:
        suite = self.get_suite(suite_id)
        if not suite:
            raise ValueError(f"Suite not found: {suite_id}")
        run = EvalRun(id=str(uuid.uuid4()), suite_id=suite_id,
                      started_at=datetime.now(), status="running")
        for case in suite.cases:
            start = time.perf_counter()
            try:
                actual = agent_fn(case.input)
                dur = (time.perf_counter() - start) * 1000
                result = scorer_fn(case, actual) if scorer_fn else self._default_scorer(case, actual, dur)
                if scorer_fn:
                    result.duration_ms = dur
            except Exception as e:
                dur = (time.perf_counter() - start) * 1000
                result = EvalResult(case_id=case.id, passed=False, score=0.0, error=str(e), duration_ms=dur)
            run.results.append(result)
        run.completed_at = datetime.now()
        run.status = "completed"
        run.summary = self._build_summary(run)
        self._runs[run.id] = run
        self._persistence.persist_run(run, self.compute_metrics(run))
        return run

    # -- Strands Evals SDK integration --
    def run_experiment(self, config: ExperimentConfig) -> ExperimentReport:
        self._require_evals()
        from .experiment_runner import run_strands_experiment
        report = run_strands_experiment(config)
        self._experiments[report.experiment_name] = report
        return report

    def generate_experiment(self, context: str, task_description: str,
                            num_cases: int = 5, evaluator_name: str = "output") -> ExperimentConfig:
        self._require_evals()
        from .experiment_runner import generate_strands_experiment
        return generate_strands_experiment(context, task_description, num_cases, evaluator_name)

    def run_simulation(self, config: ExperimentConfig, max_turns: int = 10) -> ExperimentReport:
        self._require_evals()
        from .simulator_adapter import run_simulation
        report = run_simulation(config, max_turns)
        self._experiments[report.experiment_name] = report
        return report

    def save_experiment(self, config: ExperimentConfig, filename: str) -> dict:
        self._require_evals()
        from .serialization_adapter import save_experiment
        return save_experiment(config, filename)

    def load_experiment(self, filename: str) -> ExperimentConfig:
        self._require_evals()
        from .serialization_adapter import load_experiment
        return load_experiment(filename)

    def list_saved_experiments(self) -> list[dict]:
        from .serialization_adapter import list_saved_experiments
        return list_saved_experiments()

    def list_evaluators(self) -> list[dict[str, Any]]:
        return get_available_evaluators()

    def get_experiment_report(self, name: str) -> ExperimentReport | None:
        return self._experiments.get(name)

    # -- Protocol helpers --
    def get_run(self, run_id: str) -> EvalRun | None:
        return self._runs.get(run_id)

    def list_runs(self, suite_id: str | None = None) -> list[EvalRun]:
        runs = list(self._runs.values())
        return [r for r in runs if r.suite_id == suite_id] if suite_id else runs

    def compute_metrics(self, run: EvalRun) -> EvalMetrics:
        if not run.results:
            return EvalMetrics()
        passed = sum(1 for r in run.results if r.passed)
        total = len(run.results)
        scores = [r.score for r in run.results]
        durs = [r.duration_ms for r in run.results]
        return EvalMetrics(
            total_cases=total, passed=passed, failed=total - passed,
            pass_rate=passed / total if total else 0.0,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_duration_ms=sum(durs) / len(durs) if durs else 0.0,
        )

    def health_check(self) -> EvalHealth:
        msg = ""
        if not self._evals_available:
            msg = "strands-agents-evals not installed"
        elif not self._agents_available:
            msg = "strands-agents not installed (agent execution unavailable)"
        return EvalHealth(healthy=True, backend="strands", message=msg)

    def _require_evals(self) -> None:
        if not self._evals_available:
            raise RuntimeError("strands-agents-evals not installed. pip install strands-agents-evals")

    def _default_scorer(self, case: EvalCase, actual: dict[str, Any], dur: float) -> EvalResult:
        if case.expected is None:
            return EvalResult(case_id=case.id, passed=True, score=1.0, actual=actual, duration_ms=dur)
        passed = actual == case.expected
        return EvalResult(case_id=case.id, passed=passed, score=1.0 if passed else 0.0,
                          actual=actual, duration_ms=dur)

    def _build_summary(self, run: EvalRun) -> dict[str, Any]:
        m = self.compute_metrics(run)
        return {"total": m.total_cases, "passed": m.passed, "failed": m.failed,
                "pass_rate": m.pass_rate, "avg_score": m.avg_score,
                "strands_evals_available": self._evals_available}
