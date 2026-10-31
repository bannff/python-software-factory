"""Typed boundaries for ML authoring tools."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, StrictStr


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(_Input):
    pass


class ConfigureTrainingDefaultsInput(_Input):
    batch_size: StrictInt | None = None
    learning_rate: StrictFloat | None = None
    max_seq_length: StrictInt | None = None
    optimizer: StrictStr | None = None
    lora_rank: StrictInt | None = None
    lora_alpha: StrictInt | None = None


class RegisterBaseModelInput(_Input):
    name: StrictStr
    model_id: StrictStr
    description: StrictStr = ""
    recommended_method: StrictStr = "lora"


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChronosAcquisitionOutput(_Output):
    model_id: str
    model_revision: str
    artifact: dict[str, Any]
    packages: list[dict[str, str]]


class TrainingDefaultsOutput(_Output):
    ok: bool
    defaults: dict[str, Any]


class BaseModelEntry(_Output):
    name: str
    model_id: str
    description: str
    recommended_method: str


class RegisterBaseModelOutput(_Output):
    ok: bool
    model: BaseModelEntry
    total_models: int
