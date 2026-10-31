"""Strict successful result contracts for CAN legacy projection."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .can_legacy_binding import LegacyContractArtifact, LegacyIngest, LegacyJob
from .passport_store_models import ModelPassportRef


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CanProjectedRow(_Frozen):
    rank: int = Field(gt=0)
    can_id: str
    model_id: str
    model_version: str
    model_type: str
    n_windows: int = Field(gt=0)
    n_features: int = Field(gt=0)
    window_size: int = Field(gt=0)
    label_dist: dict[str, int]
    metrics: dict[str, float]
    model_path: str
    model_digest: str
    contract_uri: str
    contract_digest: str
    passport_ref: ModelPassportRef
    passport_digest: str
    passport_revision: int = Field(gt=0)
    passport_status: Literal["published"]
    promotion_status: Literal["promotable"]
    conformance_status: Literal["passed"]
    inference_gate: Literal["passed"]
    inference_registered: Literal[False]
    registration_status: Literal["promotable"]


class CanInferenceGateResult(_Frozen):
    status: Literal["passed"]
    failed_model_types: list[str]
    promotable_model_ids: list[str]
    warm_model_ids: list[str]
    live_model_ids: list[str]


class CanProjectResult(_Frozen):
    vehicle_id: str
    ingest: LegacyIngest
    profile: LegacyJob
    contract_artifacts: dict[str, LegacyContractArtifact]
    synthesize: LegacyJob
    window: LegacyJob
    augment: LegacyJob
    top_can_ids: list[str] = Field(min_length=1)
    comparison_table: list[CanProjectedRow] = Field(min_length=1)
    model_ids: list[str] = Field(min_length=1)
    deployable_model_ids: list[str] = Field(min_length=1)
    warm_model_ids: list[str]
    inference_gate: CanInferenceGateResult
    context: dict[str, str] | None = None
    context_artifacts: dict[str, str] | None = None

    @model_validator(mode="after")
    def _bindings(self) -> "CanProjectResult":
        rows = self.comparison_table
        if self.top_can_ids != [row.can_id for row in rows]:
            raise ValueError("projected CAN-ID bindings disagree")
        if self.model_ids != [row.model_id for row in rows]:
            raise ValueError("projected model bindings disagree")
        if self.deployable_model_ids != self.model_ids or any(
            row.passport_revision != 2 for row in rows
        ):
            raise ValueError("deployable models require exact revision-two bindings")
        if self.warm_model_ids or self.inference_gate.warm_model_ids:
            raise ValueError("projection cannot authenticate process-local warm state")
        if self.inference_gate.promotable_model_ids != self.model_ids:
            raise ValueError("projected inference gate bindings disagree")
        return self


__all__ = ["CanProjectResult"]
