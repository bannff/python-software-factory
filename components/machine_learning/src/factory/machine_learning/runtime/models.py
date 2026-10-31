"""Fine-tuning domain models for machine_learning brick."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse


def _validate_uri(value: str, field_name: str) -> str:
    if not value or not urlparse(value).scheme:
        raise ValueError(f"{field_name} must be a non-empty URI")
    return value


class TrainingObjective(str, Enum):
    """Training objective — what the model learns."""

    cpt = "cpt"  # Continued Pre-Training (after AgentInstruct)
    sft = "sft"  # Supervised Fine-Tuning (after APIGen)
    dpo = "dpo"  # Direct Preference Optimization (after ReviewInstruct)


class CheckpointType(str, Enum):
    """Checkpoint artifact classification."""

    stage_artifact = "stage_artifact"  # JSONL output from pipeline stage
    training_checkpoint = "training_checkpoint"  # Model weights during training
    final_artifact = "final_artifact"  # Exported model/adapter


class FineTuningMethod(str, Enum):
    """Supported fine-tuning techniques."""

    lora = "lora"
    adalora = "adalora"
    ia3 = "ia3"
    prefix_tuning = "prefix_tuning"
    full = "full"
    mlx_lora = "mlx_lora"


class JobStatus(str, Enum):
    """Fine-tuning job lifecycle states."""

    pending = "pending"
    running = "running"
    checkpointing = "checkpointing"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


@dataclass(frozen=True)
class DatasetTrainingInput:
    """Immutable reference to a dataset view selected for training."""

    dataset_uri: str
    manifest_uri: str
    dataset_digest: str
    view_name: str
    view_schema_version: str

    def __post_init__(self) -> None:
        _validate_uri(self.dataset_uri, "dataset_uri")
        _validate_uri(self.manifest_uri, "manifest_uri")
        if len(self.dataset_digest) != 64 or any(
            character not in "0123456789abcdefABCDEF"
            for character in self.dataset_digest
        ):
            raise ValueError("dataset_digest must be a SHA-256 hex digest")
        if not self.view_name:
            raise ValueError("view_name must be non-empty")
        if not self.view_schema_version:
            raise ValueError("view_schema_version must be non-empty")


@dataclass(frozen=True)
class ResolvedTrainingDataset:
    """Backend-usable training location after dataset MCP validation."""

    training_uri: str
    dataset_uri: str
    manifest_uri: str
    dataset_digest: str
    view_name: str
    view_schema_version: str

    def __post_init__(self) -> None:
        if not self.training_uri:
            raise ValueError("training_uri must be non-empty")
        _validate_uri(self.dataset_uri, "dataset_uri")
        _validate_uri(self.manifest_uri, "manifest_uri")
        if len(self.dataset_digest) != 64 or any(
            character not in "0123456789abcdefABCDEF"
            for character in self.dataset_digest
        ):
            raise ValueError("dataset_digest must be a SHA-256 hex digest")
        if not self.view_name:
            raise ValueError("view_name must be non-empty")
        if not self.view_schema_version:
            raise ValueError("view_schema_version must be non-empty")


@dataclass
class LoRAConfig:
    """LoRA / QLoRA hyperparameters."""

    rank: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    quantization_bits: int | None = None  # None=float, 4=QLoRA-4bit, 8=QLoRA-8bit


@dataclass
class TrainingConfig:
    """Backend-agnostic training hyperparameters."""

    batch_size: int = 4
    learning_rate: float = 1e-4
    epochs: int | None = None
    max_iters: int | None = None
    gradient_accumulation_steps: int = 1
    max_seq_length: int = 512
    optimizer: str = "adamw_torch"
    seed: int = 42
    grad_checkpoint: bool = False


@dataclass
class Checkpoint:
    """A saved training checkpoint."""

    id: str
    job_id: str
    step: int
    path: str
    checkpoint_type: CheckpointType = CheckpointType.training_checkpoint
    metrics: dict[str, float] = field(default_factory=dict)
    ttl_days: int | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FineTuningJob:
    """A fine-tuning job with full lifecycle state."""

    id: str
    status: JobStatus = JobStatus.pending
    method: FineTuningMethod = FineTuningMethod.lora
    base_model: str = ""
    training_input: DatasetTrainingInput | None = None
    training_objective: TrainingObjective | None = None
    lora_config: LoRAConfig | None = None
    training_config: TrainingConfig = field(default_factory=TrainingConfig)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ModelArtifact:
    """An exported model or adapter artifact."""

    id: str
    base_model: str
    adapter_path: str | None = None
    quantization_bits: int | None = None
    source_job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
