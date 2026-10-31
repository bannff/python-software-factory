"""Strict Pydantic v2 DTOs for the passport and inference MCP families."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ..runtime.can_inference_contracts import CanPredictionSuccess
from ..runtime.model_passport import ModelPassport
from ..runtime.passport_store_models import ModelPassportPublication, ModelPassportRef


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExactPassportInput(_Input):
    model_id: str
    model_version: str
    passport_revision: StrictInt = Field(gt=0)
    passport_uri: str
    passport_digest: str

    def ref(self) -> ModelPassportRef:
        return ModelPassportRef(
            model_id=self.model_id, model_version=self.model_version,
            passport_revision=self.passport_revision, uri=self.passport_uri,
            digest=self.passport_digest,
        )


class PassportByModelInput(_Input):
    model_id: str
    model_version: str
    passport_revision: StrictInt = Field(gt=0)


class PassportOutput(ModelPassport):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PassportPromotionOutput(ModelPassportPublication):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CanPredictionInput(ExactPassportInput):
    records: list[dict[str, Any]]
    contract_digest: str


class CanPredictionOutput(CanPredictionSuccess):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NeuralPassportInput(ExactPassportInput):
    X_uri: str
    live_timing_uri: str | None = None
    live_timing_digest: str | None = None


class LiveTimingOutput(_Output):
    digest: str
    shape: list[StrictInt]


class NeuralPassportOutput(_Output):
    status: str = "completed"
    passport_ref: ModelPassportRef
    count: StrictInt = Field(gt=0)
    y_pred: list[StrictInt]
    y_score: list[float]
    live_timing: LiveTimingOutput | None = None


class WarmPredictionInput(_Input):
    records: list[dict[str, Any]]
    model_id: str
    contract_digest: str


class ModelInfoInput(_Input):
    model_id: str


class FeatureImportanceOutput(_Output):
    signal: str
    importance: float


class ModelInfoOutput(_Output):
    found: bool
    model_id: str
    model_path: str | None = None
    model_digest: str | None = None
    model_type: str | None = None
    loader_id: str | None = None
    can_id: str | None = None
    contract_uri: str | None = None
    contract_digest: str | None = None
    threshold: float | None = None
    required_shape: list[StrictInt] | None = None
    required_width: StrictInt | None = None
    passport_ref: ModelPassportRef | None = None
    passport_root: str | None = None
    prepared_x_digest: str | None = None
    prepared_y_digest: str | None = None
    materializer_config_digest: str | None = None
    inference_adapter: str | None = None
    inference_version: str | None = None
    load_error: str | None = None
    feature_importances: list[FeatureImportanceOutput] | None = None


__all__ = [
    "CanPredictionInput", "CanPredictionOutput", "ExactPassportInput",
    "ModelInfoInput", "ModelInfoOutput", "NeuralPassportInput",
    "NeuralPassportOutput", "PassportByModelInput", "PassportOutput",
    "PassportPromotionOutput", "WarmPredictionInput",
]
