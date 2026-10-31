"""Typed boundaries for ML tracking and fine-tuning operations."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, StrictStr


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateExperimentInput(_Input):
    name: StrictStr
    description: StrictStr = ""


class StartRunInput(_Input):
    experiment_id: StrictStr
    name: StrictStr = ""


class EndRunInput(_Input):
    run_id: StrictStr
    status: StrictStr = "completed"


class LogParamsInput(_Input):
    run_id: StrictStr
    params: dict[str, Any]


class LogMetricsInput(_Input):
    run_id: StrictStr
    metrics: dict[str, Any]
    step: StrictInt = 0


class CreateFineTuningJobInput(_Input):
    method: StrictStr
    base_model: StrictStr
    dataset_uri: StrictStr
    manifest_uri: StrictStr
    dataset_digest: StrictStr
    view_name: StrictStr
    view_schema_version: StrictStr
    training_objective: StrictStr | None = None
    batch_size: StrictInt = 4
    learning_rate: StrictFloat = 1e-4
    max_iters: StrictInt | None = None
    epochs: StrictInt | None = None
    max_seq_length: StrictInt = 512
    lora_rank: StrictInt = 8
    lora_alpha: StrictInt = 16
    lora_dropout: StrictFloat = 0.05
    quantization_bits: StrictInt | None = None


class JobIdInput(_Input):
    job_id: StrictStr


class ExportModelInput(JobIdInput):
    destination: StrictStr


class CleanupCheckpointsInput(_Input):
    older_than_days: StrictInt = 30
    keep_best_n: StrictInt = 3


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExperimentOutput(_Output):
    id: str
    name: str
    description: str


class RunOutput(_Output):
    id: str
    experiment_id: str | None = None
    name: str | None = None
    status: str


class LoggedFieldsOutput(_Output):
    run_id: str
    logged: list[str]
    step: int | None = None


class FineTuningJobOutput(_Output):
    id: str
    status: str
    method: str | None = None
    training_objective: str | None = None
    training_input: dict[str, str] | None = None
    metrics: dict[str, Any] | None = None
    checkpoints: int | None = None


class ExportedModelOutput(_Output):
    id: str
    base_model: str
    adapter_path: str
    source_job_id: str


class CleanupCheckpointsOutput(_Output):
    deleted: int
    older_than_days: int
    kept: int
