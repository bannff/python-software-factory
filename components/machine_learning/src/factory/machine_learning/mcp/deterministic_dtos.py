"""Strict Pydantic DTOs for deterministic ML tracking and learning reads."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_DTO):
    pass


class ExperimentListInput(_DTO):
    limit: int = 100


class LearningRunsInput(_DTO):
    limit: int = 50


class LearningSummaryInput(_DTO):
    limit: int = 200


class ExperimentIdInput(_DTO):
    experiment_id: str


class RunIdInput(_DTO):
    run_id: str


class CapabilitiesOutput(_DTO):
    name: str
    version: str
    backends: list[str]
    finetuning_backends: list[str]
    features: list[str]


class HealthTrackerOutput(_DTO):
    healthy: bool
    backend: str


class HealthOutput(_DTO):
    healthy: bool
    trackers: dict[str, HealthTrackerOutput]


class ConfigSchemaOutput(_DTO):
    type: str
    properties: dict[str, dict[str, Any]]


class ExperimentOutput(_DTO):
    found: bool
    id: str | None = None
    name: str | None = None


class ExperimentListItem(_DTO):
    id: str
    name: str


class ExperimentsOutput(_DTO):
    experiments: list[ExperimentListItem]
    count: int


class TrackingRunOutput(_DTO):
    found: bool
    id: str | None = None
    experiment_id: str | None = None
    name: str | None = None
    status: str | None = None
    params: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None


class LearningRunsOutput(_DTO):
    learning_runs: list[dict[str, Any]]
    count: int


class LearningRunOutput(_DTO):
    found: bool
    run: dict[str, Any] | None = None


class LearningSummaryOutput(_DTO):
    total_runs: int
    completed_runs: int
    rewarded_runs: int
    memory_backed_runs: int
    converged_runs: int
    average_score: float
    total_reward_value: float
    latest_updated_at: str


class LearningTimelineOutput(_DTO):
    found: bool
    events: list[str] = Field(default_factory=list)
    count: int = 0


class LearningArtifactsOutput(_DTO):
    found: bool
    artifacts: list[str] = Field(default_factory=list)
    count: int = 0
