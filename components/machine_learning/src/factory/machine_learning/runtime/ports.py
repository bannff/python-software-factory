"""Abstract ports for machine_learning brick.

Ports define what capabilities the experiment tracker needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .models import (
    Checkpoint, DatasetTrainingInput, FineTuningJob, FineTuningMethod, LoRAConfig,
    ModelArtifact, ResolvedTrainingDataset, TrainingConfig, TrainingObjective,
)


@dataclass
class TrackerHealth:
    """Health status for a tracker backend."""
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class Experiment:
    """An experiment container for runs."""
    id: str
    name: str
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Run:
    """A single experiment run."""
    id: str
    experiment_id: str
    name: str = ""
    status: str = "running"  # running, completed, failed
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)


@dataclass
class Metric:
    """A logged metric value."""
    key: str
    value: float
    step: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Dataset:
    """A versioned dataset reference."""
    id: str
    name: str
    version: str
    path: str
    digest: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ExperimentTracker(Protocol):
    """Port: Experiment tracker for ML pipelines."""

    def create_experiment(self, name: str, description: str = "", tags: dict[str, str] | None = None) -> Experiment: ...
    def get_experiment(self, experiment_id: str) -> Experiment | None: ...
    def get_experiment_by_name(self, name: str) -> Experiment | None: ...
    def list_experiments(self) -> list[Experiment]: ...
    def start_run(self, experiment_id: str, name: str = "", tags: dict[str, str] | None = None) -> Run: ...
    def end_run(self, run_id: str, status: str = "completed") -> Run: ...
    def get_run(self, run_id: str) -> Run | None: ...
    def list_runs(self, experiment_id: str | None = None) -> list[Run]: ...
    def log_param(self, run_id: str, key: str, value: Any) -> None: ...
    def log_params(self, run_id: str, params: dict[str, Any]) -> None: ...
    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None: ...
    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = 0) -> None: ...
    def log_artifact(self, run_id: str, artifact_path: str) -> None: ...
    def register_dataset(self, name: str, version: str, path: str, metadata: dict[str, Any] | None = None) -> Dataset: ...
    def get_dataset(self, name: str, version: str | None = None) -> Dataset | None: ...
    def health_check(self) -> TrackerHealth: ...


class FineTuningPort(Protocol):
    """Port: Fine-tuning job management across backends."""

    def create_job(
        self,
        method: FineTuningMethod,
        base_model: str,
        training_input: DatasetTrainingInput,
        training_config: TrainingConfig | None = None,
        lora_config: LoRAConfig | None = None,
        training_objective: TrainingObjective | None = None,
    ) -> FineTuningJob: ...

    def start_job(self, job_id: str) -> FineTuningJob: ...

    def get_job(self, job_id: str) -> FineTuningJob | None: ...

    def list_jobs(self) -> list[FineTuningJob]: ...

    def stop_job(self, job_id: str) -> FineTuningJob: ...

    def list_checkpoints(self, job_id: str) -> list[Checkpoint]: ...

    def cleanup_checkpoints(
        self, older_than_days: int = 30, keep_best_n: int = 3,
    ) -> int: ...

    def list_stage_artifacts(self, job_id: str) -> list[Checkpoint]: ...

    def export_model(self, job_id: str, destination: str) -> ModelArtifact: ...


class DatasetResolverPort(Protocol):
    """Resolve an immutable dataset view through the dataset MCP surface."""

    def resolve(self, training_input: DatasetTrainingInput) -> ResolvedTrainingDataset: ...


from .time_series_ports import (  # noqa: F401 — backward-compatible re-export
    TimeSeriesGenerationPort,
    TimeSeriesLifecycleIdentity,
    TimeSeriesLoRAConfig,
    TimeSeriesModelConfig,
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
    TimeSeriesTrainingPort,
    validate_model_config_for_family,
)
from .can_lifecycle_ports import CanLifecycleStore  # noqa: F401
from .native_lightgbm_port import NativeLightGBMPort  # noqa: F401
from .passport_ports import (  # noqa: F401
    ModelPassportConformanceRunnerPort, ModelPassportStorePort,
    ModelPassportVerifierPort,
)


__all__ = [
    "CanLifecycleStore", "Dataset", "DatasetResolverPort", "Experiment", "ExperimentTracker",
    "FineTuningPort", "Metric", "ModelPassportConformanceRunnerPort",
    "ModelPassportStorePort", "ModelPassportVerifierPort", "NativeLightGBMPort", "Run",
    "TimeSeriesGenerationPort", "TimeSeriesLifecycleIdentity",
    "TimeSeriesLoRAConfig", "TimeSeriesModelConfig",
    "TimeSeriesModelType", "TimeSeriesTrainingConfig", "TimeSeriesTrainingJob",
    "TimeSeriesTrainingPort", "TrackerHealth", "validate_model_config_for_family",
]
