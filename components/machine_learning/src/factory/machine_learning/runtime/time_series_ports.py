"""Time-series models and ports, split from the core tracking ports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .passport_refs import PassportArtifactRef
from .timeseries_identity import LifecycleIdentityView, TimeSeriesLifecycleIdentity


class TimeSeriesModelType(str, Enum):
    """Supported time-series model architectures."""

    lightgbm = "lightgbm"
    lstm = "lstm"
    tcn = "tcn"
    patchtst = "patchtst"
    chronos = "chronos"
    lnn = "lnn"
    timegan = "timegan"


@dataclass
class TimeSeriesTrainingConfig:
    """Configuration for time-series model training."""

    window_size: int = 500
    stride: int = 50
    batch_size: int = 32
    epochs: int = 50
    learning_rate: float = 1e-3
    validation_split: float = 0.2
    seed: int = 42
    early_stopping_patience: int = 10
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (1 <= self.epochs <= 10_000):
            raise ValueError(f"epochs must be in 1..10000, got {self.epochs}")
        if not (1 <= self.batch_size <= 4096):
            raise ValueError(f"batch_size must be in 1..4096, got {self.batch_size}")
        if not (1 <= self.window_size <= 10_000):
            raise ValueError(f"window_size must be in 1..10000, got {self.window_size}")


class TimeSeriesLoRAConfig(BaseModel):
    """Strict frozen LoRA input carried by the training port."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    rank: int = Field(default=8, strict=True, gt=0, le=4096)
    alpha: int = Field(default=16, strict=True, gt=0, le=65_536)
    dropout: float = Field(default=0.05, strict=True, ge=0.0, lt=1.0)
    target_modules: tuple[str, ...] = Field(
        default=(
            "self_attention.q", "self_attention.k",
            "self_attention.v", "self_attention.o",
        ),
        min_length=1, max_length=64,
    )
    quantization_bits: int | None = Field(default=None, strict=True)

    @field_validator("target_modules", mode="before")
    @classmethod
    def _target_input(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("target_modules")
    @classmethod
    def _targets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if (
            len(set(value)) != len(value)
            or any(not item.strip() or len(item) > 128 for item in value)
        ):
            raise ValueError("LoRA target modules must be unique bounded names")
        return value

    def to_runtime(self):
        """Convert at the adapter boundary to the existing native PEFT config."""
        from .models import LoRAConfig
        return LoRAConfig(
            rank=self.rank, alpha=self.alpha, dropout=self.dropout,
            target_modules=list(self.target_modules),
            quantization_bits=self.quantization_bits,
        )


class TimeSeriesModelConfig(BaseModel):
    """Strict frozen model-family inputs that flow through the training port."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    auxiliary_uris: dict[str, str] = Field(default_factory=dict, max_length=16)
    local_backbone_ref: PassportArtifactRef | None = None
    lora: bool = Field(default=False, strict=True)
    lora_config: TimeSeriesLoRAConfig | None = None

    @field_validator("auxiliary_uris")
    @classmethod
    def _auxiliary_uris(cls, value: dict[str, str]) -> dict[str, str]:
        if any(
            not isinstance(key, str) or not key.strip() or len(key) > 64
            or not isinstance(item, str) or not item.strip() or len(item) > 4096
            for key, item in value.items()
        ):
            raise ValueError("auxiliary URIs require bounded non-empty strings")
        return dict(value)

    @model_validator(mode="after")
    def _lora_pair(self) -> "TimeSeriesModelConfig":
        if self.lora != (self.lora_config is not None):
            raise ValueError("lora=true and lora_config must be declared together")
        return self


def validate_model_config_for_family(
    model_type: TimeSeriesModelType, config: TimeSeriesModelConfig | None,
) -> None:
    """Enforce closed family-specific config shapes at every dispatch boundary."""
    if model_type is TimeSeriesModelType.chronos:
        if config is None or config.local_backbone_ref is None:
            raise ValueError("Chronos requires a sealed local_backbone_ref")
        if config.auxiliary_uris:
            raise ValueError("Chronos does not accept auxiliary_uris")
        return
    if model_type is TimeSeriesModelType.lnn:
        if config is None:
            return
        if config.local_backbone_ref is not None or config.lora or config.lora_config:
            raise ValueError("LNN does not accept Chronos backbone or LoRA fields")
        if set(config.auxiliary_uris) - {"timespans"}:
            raise ValueError("LNN model_config only accepts the timespans URI")
        return
    if config is not None:
        raise ValueError(f"model_config is not supported by {model_type.value}")


@dataclass
class TimeSeriesTrainingJob(LifecycleIdentityView):
    """Lifecycle state for a time-series training job."""

    id: str
    model_type: TimeSeriesModelType
    status: str = "pending"
    experiment_id: str | None = None
    run_id: str | None = None
    config: TimeSeriesTrainingConfig = field(default_factory=TimeSeriesTrainingConfig)
    metrics: dict[str, float] = field(default_factory=dict)
    val_y_true: list[float] = field(default_factory=list)
    val_y_pred: list[float] = field(default_factory=list)
    val_y_score: list[float] = field(default_factory=list)
    model_path: str | None = None
    lifecycle_identity: TimeSeriesLifecycleIdentity | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


class TimeSeriesTrainingPort(Protocol):
    """Port: Train time-series classifiers on windowed data."""

    def train(
        self, model_type: TimeSeriesModelType, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None, experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob: ...
    def predict(self, model_id: str, X_uri: str) -> str: ...
    def get_model(self, model_id: str) -> dict[str, Any] | None: ...
    def list_models(self) -> list[dict[str, Any]]: ...
    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]: ...


class TimeSeriesGenerationPort(Protocol):
    """Port: Train and sample unsupervised time-series generators."""

    def train(
        self, X_uri: str, config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
    ) -> TimeSeriesTrainingJob: ...
    def continue_train(
        self, model_id: str, X_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        classifier_feedback: dict[str, float] | None = None,
    ) -> TimeSeriesTrainingJob: ...
    def sample(self, model_id: str, n_samples: int, *, seed: int = 42) -> str: ...
    def get_model(self, model_id: str) -> dict[str, Any] | None: ...
    def load_model(self, model_path: str) -> str: ...


__all__ = [
    "TimeSeriesGenerationPort", "TimeSeriesLifecycleIdentity",
    "TimeSeriesLoRAConfig", "TimeSeriesModelConfig", "TimeSeriesModelType",
    "TimeSeriesTrainingConfig", "TimeSeriesTrainingJob",
    "TimeSeriesTrainingPort", "validate_model_config_for_family",
]
