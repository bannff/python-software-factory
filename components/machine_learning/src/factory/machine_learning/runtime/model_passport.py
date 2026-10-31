"""Generic immutable ModelPassport domain contract."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field, field_validator, model_validator
from .can_evaluation_contracts import CanAdequacyBinding
from .can_evals_binding import MlEvalsRecordPointer
from .can_lifecycle_refs import CanLegacyBinding
from .can_passport_adequacy import validate_passport_adequacy
from .passport_refs import (
    ArchitectureBinding, FrozenModel, InferenceBinding, PassportArtifactRef,
    PassportPredecessorRef, PreparationBinding, ScenarioLineageBinding,
)
from .passport_validation import (
    require_digest, require_finite_json, require_text, semantic_digest,
)
PromotionStatus = Literal["candidate", "promotable", "rejected"]
ConformanceStatus = Literal["not_run", "passed", "failed"]
_REQUIRED_LINEAGE_ROLES = frozenset({
    "training_dataset", "training_manifest", "synthesis_dataset", "synthesis_manifest",
})

class ConformanceEvidence(FrozenModel):
    identity: str
    evidence: PassportArtifactRef
    evaluation_pointers: tuple[MlEvalsRecordPointer, ...] = ()
    model_digest: str
    inference_adapter: str
    inference_loader: str
    inference_version: str
    preparation_contract_digest: str
    prepared_x_digest: str
    prepared_y_digest: str
    materializer_config_digest: str
    prepared_timespans_digest: str | None = None
    runtime_identity: str
    probe_identity: str
    verifier_identity: str
    fresh_runtime: bool
    @field_validator(
        "identity", "inference_adapter", "inference_loader", "inference_version",
        "runtime_identity", "probe_identity", "verifier_identity",
    )
    @classmethod
    def _text(cls, value: str) -> str:
        return require_text(value, "conformance evidence identity")
    @field_validator(
        "model_digest", "preparation_contract_digest", "prepared_x_digest",
        "prepared_y_digest", "materializer_config_digest",
    )
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "conformance binding digest")
    @field_validator("prepared_timespans_digest")
    @classmethod
    def _optional_digest(cls, value: str | None) -> str | None:
        return require_digest(value, "timespans digest") if value else None

class ModelPassportBody(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    model_id: str
    model_version: str
    passport_revision: int = Field(strict=True, gt=0)
    predecessor: PassportPredecessorRef | None = None
    lineage_artifacts: tuple[PassportArtifactRef, ...] = Field(min_length=4)
    scenario_lineage: ScenarioLineageBinding | None = None
    evaluation_pointers: tuple[MlEvalsRecordPointer, ...] = ()
    evaluation_adequacy: tuple[CanAdequacyBinding, ...] = ()
    can_legacy_binding: CanLegacyBinding | None = None
    lineage_revalidated: bool
    preparation: PreparationBinding
    architecture: ArchitectureBinding
    model_artifact: PassportArtifactRef
    final_metrics: dict[str, float]
    limitations: tuple[str, ...] = Field(min_length=1)
    inference: InferenceBinding
    conformance_status: ConformanceStatus
    conformance_evidence: tuple[ConformanceEvidence, ...] = ()
    promotion_status: PromotionStatus
    rejection_reason: str | None = None
    @field_validator("model_id", "model_version")
    @classmethod
    def _identity(cls, value: str) -> str:
        return require_text(value, "model identity/version")
    @field_validator("architecture")
    @classmethod
    def _finite_config(cls, value: ArchitectureBinding) -> ArchitectureBinding:
        require_finite_json(value.config, "architecture config")
        return value
    @field_validator("final_metrics")
    @classmethod
    def _finite_metrics(cls, value: dict[str, float]) -> dict[str, float]:
        require_finite_json(value, "final metrics")
        if any(not key or key != key.strip() for key in value):
            raise ValueError("metric names must be non-empty and trimmed")
        return value
    @field_validator("limitations")
    @classmethod
    def _limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            require_text(item, "limitation")
        return value
    @field_validator("rejection_reason")
    @classmethod
    def _reason(cls, value: str | None) -> str | None:
        return require_text(value, "rejection reason") if value is not None else None
    @field_validator("lineage_artifacts")
    @classmethod
    def _sort_lineage(cls, value):
        return tuple(sorted(value, key=lambda ref: (
            ref.role, ref.identity or "", ref.version or "", ref.uri, ref.digest,
        )))
    @field_validator("conformance_evidence")
    @classmethod
    def _sort_evidence(cls, value):
        return tuple(sorted(value, key=lambda item: item.identity))
    @model_validator(mode="after")
    def _invariants(self) -> "ModelPassportBody":
        self._revision_invariants()
        roles = [item.role for item in self.lineage_artifacts]
        if len(roles) != len(set(roles)) or not _REQUIRED_LINEAGE_ROLES.issubset(roles):
            raise ValueError("lineage requires unique training/synthesis dataset and manifest roles")
        if (self.preparation.x.role, self.preparation.y.role) != ("prepared_x", "prepared_y"):
            raise ValueError("preparation X/y artifact roles are invalid")
        if self.preparation.feature_contract.role != "feature_contract":
            raise ValueError("feature contract artifact role is invalid")
        if self.model_artifact.role != "model":
            raise ValueError("model artifact role is invalid")
        validate_passport_adequacy(
            self.evaluation_pointers, self.evaluation_adequacy,
            self.promotion_status, self.model_id,
            self.can_legacy_binding.can_id if self.can_legacy_binding else None,
        )
        self._promotion_invariants()
        return self
    def _revision_invariants(self) -> None:
        if self.passport_revision == 1 and self.predecessor is not None:
            raise ValueError("passport revision 1 must not have a predecessor")
        if self.passport_revision > 1:
            prior = self.predecessor
            if prior is None or (
                prior.model_id != self.model_id or prior.model_version != self.model_version
                or prior.passport_revision != self.passport_revision - 1
            ):
                raise ValueError("passport predecessor must be the exact prior revision")
    def _promotion_invariants(self) -> None:
        if self.promotion_status == "rejected" and self.rejection_reason is None:
            raise ValueError("rejected passports require a rejection_reason")
        if self.promotion_status != "rejected" and self.rejection_reason is not None:
            raise ValueError("only rejected passports may carry a rejection_reason")
        if self.conformance_status == "not_run" and self.conformance_evidence:
            raise ValueError("not_run conformance cannot carry evidence")
        if self.promotion_status != "promotable":
            return
        if not self.lineage_revalidated or self.conformance_status != "passed":
            raise ValueError("promotable requires revalidated lineage and passed conformance")
        if not any(self._evidence_matches(item) for item in self.conformance_evidence):
            raise ValueError("promotable requires matching fresh-runtime conformance evidence")
    def _evidence_matches(self, item: ConformanceEvidence) -> bool:
        return bool(
            item.fresh_runtime and item.model_digest == self.model_artifact.digest
            and item.inference_adapter == self.inference.adapter
            and item.inference_loader == self.inference.loader
            and item.inference_version == self.inference.version
            and item.preparation_contract_digest == self.preparation.feature_contract.digest
            and item.prepared_x_digest == self.preparation.x.digest
            and item.prepared_y_digest == self.preparation.y.digest
            and item.materializer_config_digest == self.preparation.materializer.config_digest
            and item.evaluation_pointers == self.evaluation_pointers
            and item.prepared_timespans_digest == (
                self.preparation.timespans.digest if self.preparation.timespans else None
            )
        )

class ModelPassport(ModelPassportBody):
    passport_digest: str
    @field_validator("passport_digest")
    @classmethod
    def _passport_digest(cls, value: str) -> str:
        return require_digest(value, "passport digest")
    @model_validator(mode="after")
    def _digest_matches(self) -> "ModelPassport":
        exclude = {"passport_digest"}
        if not self.evaluation_adequacy:
            exclude.add("evaluation_adequacy")
        body = self.model_dump(mode="json", exclude=exclude)
        if self.passport_digest != semantic_digest(body):
            raise ValueError("passport digest does not match canonical semantic body")
        return self

__all__ = ["ConformanceEvidence", "ModelPassport", "ModelPassportBody"]
