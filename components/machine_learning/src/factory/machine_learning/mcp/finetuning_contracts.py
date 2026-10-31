"""Typed boundaries for ML fine-tuning read tools."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(_Input):
    pass


class JobIdInput(_Input):
    job_id: StrictStr


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FineTuningMethodItem(_Output):
    name: str
    description: str


class FineTuningMethodsOutput(_Output):
    methods: list[FineTuningMethodItem]


class FineTuningJobDetails(_Output):
    id: str
    status: str
    method: str
    base_model: str
    training_input: dict[str, str] | None = None
    training_objective: str | None = None
    loss: float | None = None
    lora_rank: int | None = None
    learning_rate: float | None = None
    checkpoints: int
    error: str | None = None


class JobStatusOutput(_Output):
    found: bool
    id: str | None = None
    status: str | None = None
    method: str | None = None
    base_model: str | None = None
    metrics: dict[str, Any] | None = None
    training_objective: str | None = None
    checkpoints: int | None = None
    error: str | None = None


class FineTuningJobsOutput(_Output):
    jobs: list[FineTuningJobDetails]
    count: int


class FineTuningJobOutput(_Output):
    found: bool
    id: str | None = None
    status: str | None = None
    method: str | None = None
    base_model: str | None = None
    training_input: dict[str, str] | None = None
    training_objective: str | None = None
    loss: float | None = None
    lora_rank: int | None = None
    learning_rate: float | None = None
    checkpoints: int | None = None
    error: str | None = None


class CheckpointItem(_Output):
    id: str
    step: int
    path: str
    type: str
    metrics: dict[str, Any]


class CheckpointsOutput(_Output):
    job_id: str
    checkpoints: list[CheckpointItem]


class StageArtifactsOutput(_Output):
    job_id: str
    artifacts: list[CheckpointItem]
