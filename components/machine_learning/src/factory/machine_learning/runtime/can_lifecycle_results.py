"""Strict discriminated successful-result contracts for ML CAN lifecycle."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .can_evaluation_contracts import CanEvaluationEvidence, CanEvaluatorProvenance
from .can_lifecycle_refs import CanConformanceReceiptRef
from .can_projection_results import CanProjectResult
from .passport_store_models import ModelPassportRef


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CanDigestEvidence(_Frozen):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanTrainingArtifactRef(_Frozen):
    uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: CanDigestEvidence


class CanLightGBMSeal(_Frozen):
    uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanNativeSeal(_Frozen):
    uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class _CommonPortfolioRow(_Frozen):
    rank: int = Field(gt=0)
    can_id: str
    job_id: str
    model_path: str
    metrics: dict[str, float]
    evaluation_evidence: CanEvaluationEvidence
    evaluator_provenance: CanEvaluatorProvenance
    training_config: dict[str, Any]
    artifact_refs: dict[str, CanTrainingArtifactRef]
    n_samples: int = Field(gt=0)
    window_size: int = Field(gt=0)
    n_features: int = Field(gt=0)
    label_dist: dict[str, int]
    x_shape: list[int] = Field(min_length=2)
    contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _counts(self) -> "_CommonPortfolioRow":
        if sum(self.label_dist.values()) != self.n_samples:
            raise ValueError("portfolio label distribution disagrees with sample count")
        if any(count < 0 for count in self.label_dist.values()):
            raise ValueError("portfolio label distribution cannot be negative")
        return self


class CanLightGBMPortfolioRow(_CommonPortfolioRow):
    model_family: Literal["lightgbm"]
    artifact_seal: CanLightGBMSeal

    @model_validator(mode="after")
    def _refs(self) -> "CanLightGBMPortfolioRow":
        if set(self.artifact_refs) != {"contract", "x_2d", "y"}:
            raise ValueError("LightGBM row requires exact Dataset artifact refs")
        return self


class CanNativePortfolioRow(_CommonPortfolioRow):
    model_family: Literal["lnn", "chronos"]
    training_model_config: dict[str, Any] | None = Field(
        validation_alias="model_config", serialization_alias="model_config",
    )
    artifact_seal: CanNativeSeal

    @model_validator(mode="after")
    def _refs(self) -> "CanNativePortfolioRow":
        from .can_family_specs import family_spec
        if set(self.artifact_refs) != family_spec(self.model_family).required_refs:
            raise ValueError("native row requires its exact Dataset artifact refs")
        if len(self.x_shape) != 3:
            raise ValueError("native row requires exact 3D Dataset input")
        return self


CanPortfolioRow = Annotated[
    CanLightGBMPortfolioRow | CanNativePortfolioRow,
    Field(discriminator="model_family"),
]


class CanEvaluationRecordRequest(_Frozen):
    experiment_name: str
    verdict: Literal["PASS", "FAIL"]
    pass_rate: float
    avg_score: float
    total_cases: int = Field(gt=0)
    passed: int = Field(ge=0)
    case_results: list[dict[str, Any]] = Field(min_length=1)
    evaluators_used: list[str] = Field(min_length=1)
    agent: dict[str, Any]
    timestamp: str
    source: str
    failed_cases: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    case_scores: list[float] = Field(min_length=1)
    summary: dict[str, Any]
    artifacts: dict[str, Any]
    record_kind: Literal["evaluation_run"]
    terminal_state: Literal["completed"]
    score_projection: dict[str, Any]

    @model_validator(mode="after")
    def _counts(self) -> "CanEvaluationRecordRequest":
        if (
            self.passed + self.failed_cases != self.total_cases
            or len(self.case_results) != self.total_cases
            or len(self.case_scores) != self.total_cases
        ):
            raise ValueError("evaluation record counts disagree")
        return self


class CanTrainResult(_Frozen):
    dataset_terminal: dict[str, Any]
    portfolio: list[CanPortfolioRow] = Field(min_length=1)
    can_ids: list[str] = Field(min_length=1)
    evaluation_record_request: CanEvaluationRecordRequest

    @model_validator(mode="after")
    def _ids(self) -> "CanTrainResult":
        ids = [row.can_id for row in self.portfolio]
        cases = [str(item.get("case_id")) for item in self.evaluation_record_request.case_results]
        if self.can_ids != ids or cases != ids:
            raise ValueError("training result CAN-ID bindings disagree")
        return self


class CanPassportOutcome(_Frozen):
    can_id: str
    passport_ref: ModelPassportRef


class CanPassportResult(_Frozen):
    can_ids: list[str] = Field(min_length=1)
    passport_refs: list[ModelPassportRef] = Field(min_length=1)
    passports: list[CanPassportOutcome] = Field(min_length=1)

    @model_validator(mode="after")
    def _bindings(self) -> "CanPassportResult":
        if self.can_ids != [item.can_id for item in self.passports]:
            raise ValueError("passport result CAN-ID bindings disagree")
        if self.passport_refs != [item.passport_ref for item in self.passports]:
            raise ValueError("passport result references disagree")
        return self


class CanConformanceOutcome(CanPassportOutcome):
    conformance_receipt_ref: CanConformanceReceiptRef


class CanConformanceResult(_Frozen):
    can_ids: list[str] = Field(min_length=1)
    passport_refs: list[ModelPassportRef] = Field(min_length=1)
    conformance_receipt_refs: list[CanConformanceReceiptRef] = Field(min_length=1)
    receipts: list[CanConformanceOutcome] = Field(min_length=1)

    @model_validator(mode="after")
    def _bindings(self) -> "CanConformanceResult":
        if self.can_ids != [item.can_id for item in self.receipts]:
            raise ValueError("conformance result CAN-ID bindings disagree")
        if self.passport_refs != [item.passport_ref for item in self.receipts]:
            raise ValueError("conformance passport references disagree")
        if self.conformance_receipt_refs != [
            item.conformance_receipt_ref for item in self.receipts
        ]:
            raise ValueError("conformance receipt references disagree")
        return self


__all__ = [
    "CanConformanceResult", "CanPassportResult", "CanProjectResult",
    "CanTrainResult",
]
