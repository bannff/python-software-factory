"""Frozen, closed contracts for evidence-backed multi-signal failure patterns."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .dbc_semantics import SemanticRoleBinding
from .failure_pattern_evidence import FailurePatternEvidence, FailurePatternSource
from .scenario_lineage_models import ScenarioPackRef
from .scenario_pack_models import FrozenModel, digest, text, token


class FailureRoleSpec(FrozenModel):
    role: str
    compatible_units: tuple[str, ...] = ()

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        return token(value, "semantic failure role")


class ApplicabilityPredicate(FrozenModel):
    role: str
    operator: Literal["present", "unit_in", "state_equals"]
    value: str = ""


class FailureTransform(FrozenModel):
    kind: Literal["additive_drift", "response_lag", "correlation_loss"]
    target_roles: tuple[str, ...] = Field(min_length=1)
    parameters: dict[str, float] = Field(default_factory=dict)


class FailurePhase(FrozenModel):
    phase_id: str
    start_fraction: float = Field(ge=0.0, le=1.0)
    end_fraction: float = Field(gt=0.0, le=1.0)
    severity: float = Field(gt=0.0, le=1.0)
    transforms: tuple[FailureTransform, ...] = Field(min_length=1)

    @field_validator("phase_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return token(value, "failure phase ID")

    @model_validator(mode="after")
    def _range(self) -> "FailurePhase":
        if self.end_fraction <= self.start_fraction:
            raise ValueError("failure phase range is not ordered")
        return self


class FailureConstraint(FrozenModel):
    kind: Literal["minimum_roles", "within_bounds", "maximum_delta", "mutation_required"]
    value: float = 0.0


class EventLabelPolicy(FrozenModel):
    positive_when: Literal["actual_mutation"] = "actual_mutation"
    negative_label: int = Field(default=0, strict=True)
    positive_label: int = Field(default=1, strict=True)


class FailurePatternDraft(FrozenModel):
    pattern_id: str
    version: str
    title: str
    sources: tuple[FailurePatternSource, ...] = Field(min_length=1)
    evidence: tuple[FailurePatternEvidence, ...] = Field(min_length=1)
    roles: tuple[FailureRoleSpec, ...] = Field(min_length=2)
    applicability: tuple[ApplicabilityPredicate, ...] = ()
    phases: tuple[FailurePhase, ...] = Field(min_length=1)
    constraints: tuple[FailureConstraint, ...] = Field(min_length=1)
    event_label_policy: EventLabelPolicy = EventLabelPolicy()

    @field_validator("pattern_id", "version")
    @classmethod
    def _ids(cls, value: str) -> str:
        return token(value, "failure pattern identity/version")

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return text(value, "failure pattern title")

    @model_validator(mode="after")
    def _ordered(self) -> "FailurePatternDraft":
        role_names = [item.role for item in self.roles]
        if len(role_names) != len(set(role_names)):
            raise ValueError("failure pattern roles must be unique")
        sources = {item.source_id: item for item in self.sources}
        source_ids = set(sources)
        if len(source_ids) != len(self.sources):
            raise ValueError("failure pattern sources must be unique")
        if any(item.source_id not in source_ids for item in self.evidence):
            raise ValueError("failure evidence references an unknown source")
        if any(item.range_end > len(sources[item.source_id].retrieved_content)
               for item in self.evidence):
            raise ValueError("failure evidence range exceeds retrieved source content")
        predicates = {item.role for item in self.applicability}
        if not set(role_names).issubset(predicates):
            raise ValueError("every failure role requires an applicability predicate")
        constraint_kinds = {item.kind for item in self.constraints}
        minimum = max((item.value for item in self.constraints
                       if item.kind == "minimum_roles"), default=0)
        if "mutation_required" not in constraint_kinds or minimum < 2:
            raise ValueError("failure patterns require mutation and multi-role constraints")
        previous = 0.0
        for phase in self.phases:
            if phase.start_fraction < previous:
                raise ValueError("failure pattern phases must be ordered and non-overlapping")
            previous = phase.end_fraction
            targets = {role for transform in phase.transforms for role in transform.target_roles}
            if not targets.issubset(role_names):
                raise ValueError("failure transform references undeclared role")
        return self


class FailurePatternSpec(FailurePatternDraft):
    digest: str

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "failure pattern")


class FailurePatternRef(FrozenModel):
    pattern_id: str
    version: str
    digest: str

    @field_validator("pattern_id", "version")
    @classmethod
    def _ids(cls, value: str) -> str:
        return token(value, "failure pattern reference")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return digest(value, "failure pattern reference")


class FailurePatternBinding(FrozenModel):
    pattern: FailurePatternRef
    dbc_definition_id: str
    bindings: tuple[SemanticRoleBinding, ...] = Field(min_length=2)
    binding_digest: str


class FailurePatternLineage(FrozenModel):
    deterministic_seed: int = Field(strict=True, ge=0)
    dbc_version: str
    dbc_digest: str
    pattern: FailurePatternRef
    scenario_pack: ScenarioPackRef
    binding_digest: str
    constraint_digest: str
    applicability_digest: str
    event_ids: tuple[str, ...]
    input_digest: str
    output_digest: str


class FailureBindingReport(FrozenModel):
    status: Literal["bound", "invalid"]
    binding: FailurePatternBinding | None = None
    missing_roles: tuple[str, ...] = ()
    ambiguous_roles: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    incompatible_roles: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    errors: tuple[str, ...] = ()
