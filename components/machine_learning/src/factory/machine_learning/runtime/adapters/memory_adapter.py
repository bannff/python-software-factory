"""Memory adapter for experiment tracking brick.

Provides in-memory experiment tracking for development and testing.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime
from typing import Any

from ..ports import (
    Experiment,
    Run,
    Dataset,
    TrackerHealth,
)


class MemoryTracker:
    """In-memory experiment tracker adapter."""

    def __init__(self, **kwargs: Any) -> None:
        self._experiments: dict[str, Experiment] = {}
        self._runs: dict[str, Run] = {}
        self._datasets: dict[str, Dataset] = {}

    def create_experiment(
        self,
        name: str,
        description: str = "",
        tags: dict[str, str] | None = None,
    ) -> Experiment:
        """Create an experiment."""
        exp = Experiment(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            tags=tags or {},
        )
        self._experiments[exp.id] = exp
        # Persist to knowledge graph (fire-and-forget, never blocks)
        try:
            from .graph_adapter import GraphMLStore
            GraphMLStore().persist_experiment(exp)
        except Exception:
            pass  # Graph persistence is optional
        return exp

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def get_experiment_by_name(self, name: str) -> Experiment | None:
        """Get an experiment by name."""
        for exp in self._experiments.values():
            if exp.name == name:
                return exp
        return None

    def list_experiments(self) -> list[Experiment]:
        """List all experiments."""
        return list(self._experiments.values())

    def start_run(
        self,
        experiment_id: str,
        name: str = "",
        tags: dict[str, str] | None = None,
    ) -> Run:
        """Start a new run in an experiment."""
        run = Run(
            id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            name=name or f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            status="running",
            tags=tags or {},
        )
        self._runs[run.id] = run
        return run

    def end_run(self, run_id: str, status: str = "completed") -> Run:
        """End a run."""
        run = self._runs.get(run_id)
        if run:
            run.status = status
            run.ended_at = datetime.now()
            # Persist to knowledge graph (fire-and-forget, never blocks)
            try:
                from .graph_adapter import GraphMLStore
                GraphMLStore().persist_run(run)
            except Exception:
                pass  # Graph persistence is optional
        return run

    def get_run(self, run_id: str) -> Run | None:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, experiment_id: str | None = None) -> list[Run]:
        """List runs, optionally filtered by experiment."""
        runs = list(self._runs.values())
        if experiment_id:
            runs = [r for r in runs if r.experiment_id == experiment_id]
        return runs

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Log a parameter to a run."""
        run = self._runs.get(run_id)
        if run:
            run.params[key] = value

    def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        """Log multiple parameters to a run."""
        run = self._runs.get(run_id)
        if run:
            run.params.update(params)

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        """Log a metric to a run."""
        run = self._runs.get(run_id)
        if run:
            run.metrics[key] = value

    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = 0) -> None:
        """Log multiple metrics to a run."""
        run = self._runs.get(run_id)
        if run:
            run.metrics.update(metrics)

    def log_artifact(self, run_id: str, artifact_path: str) -> None:
        """Log an artifact to a run."""
        run = self._runs.get(run_id)
        if run:
            run.artifacts.append(artifact_path)

    def register_dataset(
        self,
        name: str,
        version: str,
        path: str,
        metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        """Register a dataset version."""
        digest = hashlib.sha256(f"{name}:{version}:{path}".encode()).hexdigest()[:16]
        dataset = Dataset(
            id=str(uuid.uuid4()),
            name=name,
            version=version,
            path=path,
            digest=digest,
            metadata=metadata or {},
        )
        self._datasets[f"{name}:{version}"] = dataset
        return dataset

    def get_dataset(self, name: str, version: str | None = None) -> Dataset | None:
        """Get a dataset by name and optional version."""
        if version:
            return self._datasets.get(f"{name}:{version}")
        # Return latest version
        matching = [d for k, d in self._datasets.items() if k.startswith(f"{name}:")]
        return matching[-1] if matching else None

    def health_check(self) -> TrackerHealth:
        """Check tracker health."""
        start = time.perf_counter()
        latency = (time.perf_counter() - start) * 1000
        return TrackerHealth(healthy=True, backend="memory", latency_ms=latency)
