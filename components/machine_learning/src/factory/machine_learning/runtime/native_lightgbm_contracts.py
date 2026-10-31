"""Typed bounded JSON contract for isolated native LightGBM operations."""
from __future__ import annotations

import math
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

Operation: TypeAlias = Literal[
    "fit_predict_persist", "inspect_mlflow", "inspect_joblib",
    "score_mlflow", "score_joblib",
]
PathText = Annotated[str, Field(min_length=1, max_length=4096)]
Probabilities = Annotated[list[list[float]], Field(max_length=200_000)]
Importances = Annotated[list[float], Field(max_length=100_000)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FitPayload(_StrictModel):
    x_uri: PathText
    y_uri: PathText
    destination: PathText
    validation_x_uri: PathText | None = None
    validation_y_uri: PathText | None = None
    init_model: PathText | None = None
    validation_split: float = Field(gt=0.0, lt=1.0)
    seed: int = Field(ge=0, le=2_147_483_647)
    training_mode: Literal["standard", "transfer"] = "standard"
    rounds: int = Field(default=100, ge=1, le=1_000)
    scale_pos_weight: float | None = Field(default=None, gt=0.0, le=1_000_000.0)
    class_weight: Literal["balanced"] | dict[str, float] | None = None

    @model_validator(mode="after")
    def _fit_contract(self):
        if (self.validation_x_uri is None) != (self.validation_y_uri is None):
            raise ValueError("validation array URIs must be paired")
        expected = 50 if self.training_mode == "transfer" and self.init_model else 100
        if self.rounds != expected:
            raise ValueError("LightGBM rounds disagree with the bounded training mode")
        if self.training_mode == "standard" and self.init_model is not None:
            raise ValueError("standard LightGBM training cannot continue a model")
        return self

    @field_validator("class_weight")
    @classmethod
    def _bounded_class_weight(cls, value):
        if isinstance(value, dict):
            if len(value) > 2 or set(value) - {"0", "1"} or any(
                weight <= 0.0 or weight > 1_000_000.0 for weight in value.values()
            ):
                raise ValueError("class_weight is outside the bounded binary protocol")
        return value


class ArtifactPayload(_StrictModel):
    source: PathText
    expected_width: int | None = Field(default=None, ge=1, le=100_000)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class ScorePayload(ArtifactPayload):
    values_uri: PathText


class FitRequest(_StrictModel):
    version: Literal["1.0"] = "1.0"
    operation: Literal["fit_predict_persist"]
    payload: FitPayload


class InspectRequest(_StrictModel):
    version: Literal["1.0"] = "1.0"
    operation: Literal["inspect_mlflow", "inspect_joblib"]
    payload: ArtifactPayload


class ScoreRequest(_StrictModel):
    version: Literal["1.0"] = "1.0"
    operation: Literal["score_mlflow", "score_joblib"]
    payload: ScorePayload


NativeRequest = Annotated[
    FitRequest | InspectRequest | ScoreRequest, Field(discriminator="operation"),
]


class NativeMetadata(_StrictModel):
    width: int = Field(ge=1, le=100_000)
    threshold: float = Field(ge=0.0, le=1.0)
    importances: Importances

    @model_validator(mode="after")
    def _importance_width(self):
        if (
            len(self.importances) != self.width
            or any(not math.isfinite(value) or value < 0.0 for value in self.importances)
        ):
            raise ValueError("native feature importances are invalid")
        return self


class FitResult(NativeMetadata):
    kind: Literal["fit"] = "fit"
    probabilities: Probabilities
    iterations: int = Field(ge=1, le=1_000_000)

    @model_validator(mode="after")
    def _binary_probabilities(self):
        if not _valid_probabilities(self.probabilities):
            raise ValueError("native fit probabilities are not binary")
        return self


class InspectResult(NativeMetadata):
    kind: Literal["inspect"] = "inspect"


class ScoreResult(NativeMetadata):
    kind: Literal["score"] = "score"
    probabilities: Probabilities

    @model_validator(mode="after")
    def _binary_probabilities(self):
        if not _valid_probabilities(self.probabilities):
            raise ValueError("native score probabilities are not binary")
        return self


def _valid_probabilities(rows: list[list[float]]) -> bool:
    return all(
        len(row) == 2
        and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in row)
        and math.isclose(sum(row), 1.0, rel_tol=0.0, abs_tol=1e-9)
        for row in rows
    )


NativeResult = FitResult | InspectResult | ScoreResult


class NativeSuccess(_StrictModel):
    ok: Literal[True]
    operation: Operation
    result: Annotated[NativeResult, Field(discriminator="kind")]


class NativeFailure(_StrictModel):
    ok: Literal[False]
    operation: Operation
    error: Annotated[str, Field(min_length=1, max_length=512)]


NativeResponse = Annotated[
    NativeSuccess | NativeFailure, Field(discriminator="ok"),
]
REQUEST_ADAPTER = TypeAdapter(NativeRequest)
RESPONSE_ADAPTER = TypeAdapter(NativeResponse)

__all__ = [
    "ArtifactPayload", "FitPayload", "FitRequest", "FitResult", "InspectRequest",
    "InspectResult", "NativeFailure", "NativeRequest", "NativeResponse",
    "NativeResult", "NativeSuccess", "REQUEST_ADAPTER", "RESPONSE_ADAPTER",
    "ScorePayload", "ScoreRequest", "ScoreResult",
]
