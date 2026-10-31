"""Strict immutable contracts for CAN evaluation policy and adequacy."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .can_lifecycle_refs import CanEvalsPointer

MetricName = Literal["accuracy", "precision", "recall", "f1", "auroc", "auprc", "brier"]
MetricState = Literal["valid", "missing", "nonfinite", "out_of_range"]
SplitKind = Literal["ordered_holdout", "seeded_shuffle_sensitivity"]
Verdict = Literal["PASS", "FAIL"]
CAN_EVIDENCE_SCHEMA = "evals.can-model-evidence"
CAN_EVIDENCE_VERSION = "1.0"
CAN_EVALUATOR_IDENTITY = "evals.can-model@v1"


class FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CanMetricRule(FrozenContract):
    metric: MetricName
    operator: Literal["gte", "lte"]
    threshold: float = Field(ge=0.0, le=1.0)


class CanEvaluationPolicy(FrozenContract):
    policy_id: str
    policy_version: str
    scope: Literal["synthetic_sensitivity"]
    required_split_kind: Literal["ordered_holdout"]
    min_validation_rows: int = Field(ge=1)
    min_positive_rows: int = Field(ge=1)
    min_negative_rows: int = Field(ge=1)
    metric_rules: tuple[CanMetricRule, ...] = Field(min_length=1)
    score_metric: Literal["f1"]
    promotion_eligible: bool

    @property
    def identity(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"


class CanEvaluationEvidence(FrozenContract):
    scope: Literal["synthetic_sensitivity"]
    split_kind: SplitKind
    validation_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _counts(self) -> "CanEvaluationEvidence":
        if self.positive_count + self.negative_count != self.validation_count:
            raise ValueError("validation class counts must equal validation_count")
        return self


class CanEvaluatorProvenance(FrozenContract):
    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, serialize_by_alias=True,
    )

    schema_name: Literal["evals.can-model-evidence"] = Field(alias="schema")
    version: Literal["1.0"]
    evaluator_identity: Literal["evals.can-model@v1"]
    input_digest: str

    @field_validator("input_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_sha256(value, "evaluator input digest")


class CanCaseAdequacy(FrozenContract):
    case_id: str
    model_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    evidence: CanEvaluationEvidence
    evaluator_provenance: CanEvaluatorProvenance
    metrics: dict[str, float | None]
    metric_states: dict[str, MetricState]
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[str, ...]
    promotion_eligible: bool

    @field_validator("case_id", "model_id", "policy_id", "policy_version")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("evaluation identity must be non-empty and trimmed")
        return value

    @field_validator("policy_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_sha256(value, "policy_digest")


class CanRunAdequacy(FrozenContract):
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: Literal["synthetic_sensitivity"]
    promotion_eligible: bool
    verdict: Verdict
    total_cases: int = Field(gt=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    avg_score: float = Field(ge=0.0, le=1.0)
    cases: tuple[CanCaseAdequacy, ...] = Field(min_length=1)


class CanAdequacyBinding(FrozenContract):
    pointer: CanEvalsPointer
    run_id: str
    case_id: str
    model_id: str
    evaluator_identity: Literal["evals.can-model@v1"]
    input_digest: str
    case_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    scope: Literal["synthetic_sensitivity"]
    run_verdict: Verdict
    run_promotion_eligible: bool
    summary_digest: str

    @field_validator("run_id", "case_id", "model_id", "policy_id", "policy_version")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("adequacy binding identity must be non-empty and trimmed")
        return value

    @field_validator("input_digest", "case_digest", "policy_digest", "summary_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _require_sha256(value, "adequacy binding digest")


class CanVerifiedEvaluationRecord(FrozenContract):
    pointer: CanEvalsPointer
    run_id: str
    adequacy: CanRunAdequacy
    bindings: tuple[CanAdequacyBinding, ...] = Field(min_length=1)

    def binding_for(self, model_id: str, case_id: str) -> CanAdequacyBinding:
        matches = tuple(
            item for item in self.bindings
            if item.model_id == model_id and item.case_id == case_id
        )
        if len(matches) != 1:
            raise ValueError("verified Evals record lacks one exact case binding")
        return matches[0]

    @property
    def binding(self) -> CanAdequacyBinding:
        if len(self.bindings) != 1:
            raise ValueError("multi-case evaluation record has no singular binding")
        return self.bindings[0]


def _require_sha256(value: str, field: str) -> str:
    if len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(f"{field} must be sha256-prefixed")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError(f"{field} must contain lowercase hexadecimal") from exc
    if value[7:] != value[7:].lower():
        raise ValueError(f"{field} must contain lowercase hexadecimal")
    return value


__all__ = [
    "CanAdequacyBinding", "CanCaseAdequacy", "CanEvaluationEvidence",
    "CanEvaluationPolicy", "CanEvaluatorProvenance", "CanMetricRule",
    "CanRunAdequacy", "CanVerifiedEvaluationRecord", "MetricName", "MetricState",
    "SplitKind", "CAN_EVALUATOR_IDENTITY",
]
