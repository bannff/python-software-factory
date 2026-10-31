"""Evaluation persistence adapters and runtime composition."""
from __future__ import annotations

from typing import Any

from ..ports import EvalMetrics, EvalPersistencePort, EvalRun, EvalSuite


class NoOpEvalPersistence:
    """Default persistence adapter that intentionally performs no writes."""

    def persist_suite(self, suite: EvalSuite) -> None:
        """Accept a suite without persisting it."""

    def persist_run(self, run: EvalRun, metrics: EvalMetrics) -> None:
        """Accept a run without persisting it."""


def build_eval_persistence(config: dict[str, Any]) -> EvalPersistencePort:
    """Compose the configured persistence adapter for an Evals runtime."""
    backend = config.get("persistence", "noop")
    if backend == "noop":
        return NoOpEvalPersistence()
    if backend == "graph":
        from .graph_adapter import GraphEvalsStore
        return GraphEvalsStore()
    raise ValueError(f"Unknown eval persistence backend: {backend}")
