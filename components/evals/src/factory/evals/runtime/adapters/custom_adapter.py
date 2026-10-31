"""Custom adapter for evals brick.

Provides in-memory evaluation runner for custom benchmarks.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Callable

from ..ports import (
    EvalCase,
    EvalResult,
    EvalSuite,
    EvalRun,
    EvalMetrics,
    EvalHealth,
    EvalPersistencePort,
)
from .persistence import NoOpEvalPersistence


class CustomEvalRunner:
    """Custom in-memory evaluation runner."""

    def __init__(
        self, persistence: EvalPersistencePort | None = None, **kwargs: Any,
    ) -> None:
        self._suites: dict[str, EvalSuite] = {}
        self._runs: dict[str, EvalRun] = {}
        self._persistence = (
            persistence if persistence is not None else NoOpEvalPersistence()
        )

    def create_suite(self, suite: EvalSuite) -> EvalSuite:
        """Create an evaluation suite."""
        self._suites[suite.id] = suite
        self._persistence.persist_suite(suite)
        return suite

    def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Get an evaluation suite by ID."""
        return self._suites.get(suite_id)

    def list_suites(self) -> list[EvalSuite]:
        """List all evaluation suites."""
        return list(self._suites.values())

    def run_suite(
        self,
        suite_id: str,
        agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
        scorer_fn: Callable[[EvalCase, dict[str, Any]], EvalResult] | None = None,
    ) -> EvalRun:
        """Run an evaluation suite against an agent."""
        suite = self.get_suite(suite_id)
        if not suite:
            raise ValueError(f"Suite not found: {suite_id}")

        run = EvalRun(
            id=str(uuid.uuid4()),
            suite_id=suite_id,
            started_at=datetime.now(),
            status="running",
        )

        for case in suite.cases:
            start = time.perf_counter()
            try:
                actual = agent_fn(case.input)
                duration = (time.perf_counter() - start) * 1000

                if scorer_fn:
                    result = scorer_fn(case, actual)
                    result.duration_ms = duration
                else:
                    result = self._default_scorer(case, actual, duration)

            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                result = EvalResult(
                    case_id=case.id,
                    passed=False,
                    score=0.0,
                    error=str(e),
                    duration_ms=duration,
                )

            run.results.append(result)

        run.completed_at = datetime.now()
        run.status = "completed"
        run.summary = self._compute_summary(run)
        self._runs[run.id] = run
        self._persistence.persist_run(run, self.compute_metrics(run))
        return run

    def _default_scorer(
        self,
        case: EvalCase,
        actual: dict[str, Any],
        duration_ms: float,
    ) -> EvalResult:
        """Default scorer - exact match on expected output."""
        if case.expected is None:
            return EvalResult(
                case_id=case.id,
                passed=True,
                score=1.0,
                actual=actual,
                duration_ms=duration_ms,
            )

        passed = actual == case.expected
        return EvalResult(
            case_id=case.id,
            passed=passed,
            score=1.0 if passed else 0.0,
            actual=actual,
            duration_ms=duration_ms,
        )

    def _compute_summary(self, run: EvalRun) -> dict[str, Any]:
        """Compute summary statistics for a run."""
        metrics = self.compute_metrics(run)
        return {
            "total": metrics.total_cases,
            "passed": metrics.passed,
            "failed": metrics.failed,
            "pass_rate": metrics.pass_rate,
            "avg_score": metrics.avg_score,
            "avg_duration_ms": metrics.avg_duration_ms,
        }

    def get_run(self, run_id: str) -> EvalRun | None:
        """Get an evaluation run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, suite_id: str | None = None) -> list[EvalRun]:
        """List evaluation runs, optionally filtered by suite."""
        runs = list(self._runs.values())
        if suite_id:
            runs = [r for r in runs if r.suite_id == suite_id]
        return runs

    def compute_metrics(self, run: EvalRun) -> EvalMetrics:
        """Compute aggregated metrics from a run."""
        if not run.results:
            return EvalMetrics()

        passed = sum(1 for r in run.results if r.passed)
        total = len(run.results)
        scores = [r.score for r in run.results]
        durations = [r.duration_ms for r in run.results]

        return EvalMetrics(
            total_cases=total,
            passed=passed,
            failed=total - passed,
            pass_rate=passed / total if total > 0 else 0.0,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_duration_ms=sum(durations) / len(durations) if durations else 0.0,
        )

    def health_check(self) -> EvalHealth:
        """Check runner health."""
        start = time.perf_counter()
        latency = (time.perf_counter() - start) * 1000
        return EvalHealth(healthy=True, backend="custom", latency_ms=latency)
