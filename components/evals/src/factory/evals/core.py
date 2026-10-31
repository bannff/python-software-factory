"""Core convenience functions for evals brick."""

from __future__ import annotations

from typing import Any, Callable

from .runtime.ports import EvalCase, EvalResult, EvalSuite, EvalRun, EvalMetrics
from .runtime.runtime import get_runtime


def create_suite(
    suite_id: str,
    name: str,
    cases: list[EvalCase] | None = None,
    description: str = "",
    backend: str = "custom",
) -> EvalSuite:
    """Create an evaluation suite."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    suite = EvalSuite(id=suite_id, name=name, description=description, cases=cases or [])
    return runner.create_suite(suite)


def get_suite(suite_id: str, backend: str = "custom") -> EvalSuite | None:
    """Get an evaluation suite by ID."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.get_suite(suite_id)


def list_suites(backend: str = "custom") -> list[EvalSuite]:
    """List all evaluation suites."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.list_suites()


def run_suite(
    suite_id: str,
    agent_fn: Callable[[dict[str, Any]], dict[str, Any]],
    scorer_fn: Callable[[EvalCase, dict[str, Any]], EvalResult] | None = None,
    backend: str = "custom",
) -> EvalRun:
    """Run an evaluation suite against an agent."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.run_suite(suite_id, agent_fn, scorer_fn)


def get_run(run_id: str, backend: str = "custom") -> EvalRun | None:
    """Get an evaluation run by ID."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.get_run(run_id)


def list_runs(suite_id: str | None = None, backend: str = "custom") -> list[EvalRun]:
    """List evaluation runs."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.list_runs(suite_id)


def compute_metrics(run: EvalRun, backend: str = "custom") -> EvalMetrics:
    """Compute aggregated metrics from a run."""
    runtime = get_runtime()
    runner = runtime.get_runner(backend)
    return runner.compute_metrics(run)
