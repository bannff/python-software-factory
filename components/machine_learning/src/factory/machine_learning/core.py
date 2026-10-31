"""Core convenience functions for machine_learning brick."""

from __future__ import annotations

from typing import Any

from .runtime.ports import Experiment, Run, Dataset
from .runtime.runtime import get_runtime


def create_experiment(
    name: str,
    description: str = "",
    tags: dict[str, str] | None = None,
    backend: str = "memory",
) -> Experiment:
    """Create an experiment."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.create_experiment(name, description, tags)


def get_experiment(experiment_id: str, backend: str = "memory") -> Experiment | None:
    """Get an experiment by ID."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.get_experiment(experiment_id)


def list_experiments(backend: str = "memory") -> list[Experiment]:
    """List all experiments."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.list_experiments()


def start_run(
    experiment_id: str,
    name: str = "",
    tags: dict[str, str] | None = None,
    backend: str = "memory",
) -> Run:
    """Start a new run in an experiment."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.start_run(experiment_id, name, tags)


def end_run(run_id: str, status: str = "completed", backend: str = "memory") -> Run:
    """End a run."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.end_run(run_id, status)


def get_run(run_id: str, backend: str = "memory") -> Run | None:
    """Get a run by ID."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.get_run(run_id)


def log_params(run_id: str, params: dict[str, Any], backend: str = "memory") -> None:
    """Log parameters to a run."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    tracker.log_params(run_id, params)


def log_metrics(run_id: str, metrics: dict[str, float], step: int = 0, backend: str = "memory") -> None:
    """Log metrics to a run."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    tracker.log_metrics(run_id, metrics, step)


def register_dataset(
    name: str,
    version: str,
    path: str,
    metadata: dict[str, Any] | None = None,
    backend: str = "memory",
) -> Dataset:
    """Register a dataset version."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.register_dataset(name, version, path, metadata)


def get_dataset(name: str, version: str | None = None, backend: str = "memory") -> Dataset | None:
    """Get a dataset by name and optional version."""
    runtime = get_runtime()
    tracker = runtime.get_tracker(backend)
    return tracker.get_dataset(name, version)
