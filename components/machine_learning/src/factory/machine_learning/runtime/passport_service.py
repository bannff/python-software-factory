"""Port-injected service for server-issued and trusted ModelPassports."""
from __future__ import annotations

from .adapters.sealed_probe_store import SealedProbeStore
from .can_evaluation_contracts import CanAdequacyBinding
from .can_passport_adequacy import require_promotion_adequacy
from .model_passport import ConformanceEvidence, ModelPassport
from .passport_evidence import derive_conformance_evidence
from .passport_codec import create_model_passport, load_model_passport
from .passport_ports import (
    ModelPassportConformanceRunnerPort, ModelPassportStorePort,
    ModelPassportVerifierPort,
)
from .passport_native_contract import native_conformance_identity
from .passport_refs import PassportArtifactRef, PassportPredecessorRef
from .passport_store_models import ModelPassportPublication, ModelPassportRef
from .passport_validation import canonical_json

_ALLOWED_PROMOTION_CHANGES = {
    "passport_revision", "predecessor", "limitations", "conformance_status",
    "conformance_evidence", "promotion_status", "passport_digest",
}


class ModelPassportService:
    """Apply issuance, retrieval, and promotion policy around injected ports."""

    def __init__(
        self, *, store: ModelPassportStorePort,
        verifier: ModelPassportVerifierPort,
        conformance_runner: ModelPassportConformanceRunnerPort | None = None,
        storage_root: str | None = None,
    ) -> None:
        self._store = store
        self._verifier = verifier
        self._conformance_runner = conformance_runner
        self.storage_root = storage_root

    def issue_candidate(self, passport: ModelPassport) -> ModelPassportPublication:
        """Admit only a server-assembled revision-one untested candidate."""
        value = load_model_passport(passport)
        if not _is_candidate(value):
            raise ValueError("issuance requires exact revision-1 candidate/not_run")
        self._verifier.verify(value)
        return self._store.publish(value)

    def record_rejected(self, passport: ModelPassport) -> ModelPassportPublication:
        """Preserve existing internal non-deployable records for other families."""
        value = load_model_passport(passport)
        if value.passport_revision != 1 or value.promotion_status != "rejected":
            raise ValueError("rejected recording requires server revision one")
        self._verifier.verify(value)
        return self._store.publish(value)

    def get(self, ref: ModelPassportRef) -> ModelPassport:
        value = self._store.get(ref)
        self._verifier.verify(value)
        return value

    def get_by_model(
        self, model_id: str, model_version: str, passport_revision: int,
    ) -> ModelPassport:
        value = self._store.get_by_model(model_id, model_version, passport_revision)
        self._verifier.verify(value)
        return value

    def generate_conformance(
        self, ref: ModelPassportRef, *, effect_id: str | None = None,
    ) -> ConformanceEvidence:
        """Collect evidence for an exact candidate without publishing a passport."""
        candidate = self.get(ref)
        if not _is_candidate(candidate):
            raise ValueError("trusted conformance requires an exact revision-1 candidate")
        if self._conformance_runner is None:
            raise ValueError("trusted conformance runner is not configured")
        if effect_id is None:
            return self._conformance_runner.run(candidate, ref)
        return self._conformance_runner.run(candidate, ref, effect_id=effect_id)

    def promote_lifecycle(
        self, ref: ModelPassportRef, receipt_evidence: dict,
        *, effect_id: str, evaluation_pointers: tuple,
        evaluation_adequacy: tuple[CanAdequacyBinding, ...],
    ) -> ModelPassportPublication:
        """Re-derive lifecycle evidence from sealed bytes and invoke no probe."""
        candidate = self.get(ref)
        if not _is_candidate(candidate):
            raise ValueError("trusted promotion requires an exact revision-1 candidate")
        require_promotion_adequacy(
            candidate.evaluation_pointers, candidate.evaluation_adequacy,
            evaluation_adequacy,
        )
        serialized = ConformanceEvidence.model_validate_json(canonical_json(receipt_evidence))
        artifact = PassportArtifactRef.model_validate(serialized.evidence)
        if not self.storage_root:
            raise ValueError("trusted lifecycle evidence storage is not configured")
        store = SealedProbeStore(self.storage_root)
        try:
            evidence = derive_conformance_evidence(
                candidate=candidate, nonce=effect_id, artifact=artifact, store=store,
                evaluation_pointers=evaluation_pointers, reject_current_pid=False,
            )
        finally:
            store.close()
        if serialized != evidence:
            raise ValueError("serialized conformance receipt disagrees with sealed probe")
        return self.promote(
            ref, evidence, evaluation_adequacy=evaluation_adequacy,
        )

    def promote(
        self, ref: ModelPassportRef, evidence: ConformanceEvidence,
        *, evaluation_adequacy: tuple[CanAdequacyBinding, ...] = (),
    ) -> ModelPassportPublication:
        """Publish revision two from supplied trusted evidence; invoke no runner."""
        candidate = self.get(ref)
        if not _is_candidate(candidate):
            raise ValueError("trusted promotion requires an exact revision-1 candidate")
        require_promotion_adequacy(
            candidate.evaluation_pointers, candidate.evaluation_adequacy,
            evaluation_adequacy,
        )
        if evidence.evaluation_pointers != candidate.evaluation_pointers:
            raise ValueError("conformance evidence changes exact Evals pointer bindings")
        body = candidate.model_dump(mode="python", exclude={"passport_digest"})
        limitations = ["Trusted isolated native CAN conformance passed."]
        if candidate.inference.loader == "chronos.Chronos2Pipeline":
            limitations.append(
                "Pooled Chronos-2 CAN classifier probe; not a forecasting model."
            )
        body.update({
            "passport_revision": 2,
            "predecessor": PassportPredecessorRef.model_validate(ref.model_dump()),
            "limitations": tuple(limitations),
            "conformance_status": "passed", "conformance_evidence": (evidence,),
            "promotion_status": "promotable",
        })
        promoted = create_model_passport(**body)
        _require_copy_forward(candidate, promoted, ref)
        self._verifier.verify(promoted)
        existing = self._existing_promotion(candidate, ref)
        if existing is not None:
            return existing
        return self._store.publish(promoted)

    def verify_and_promote(self, ref: ModelPassportRef) -> ModelPassportPublication:
        """Backward-compatible composition of evidence generation and promotion."""
        candidate = self.get(ref)
        if not _is_candidate(candidate):
            raise ValueError("trusted promotion requires an exact revision-1 candidate")
        existing = self._existing_promotion(candidate, ref)
        if existing is not None:
            return existing
        return self.promote(ref, self.generate_conformance(ref))

    def _existing_promotion(
        self, candidate: ModelPassport, ref: ModelPassportRef,
    ) -> ModelPassportPublication | None:
        try:
            existing = self.get_by_model(candidate.model_id, candidate.model_version, 2)
        except KeyError:
            return None
        _require_copy_forward(candidate, existing, ref)
        return self._store.publish(existing)


def _is_candidate(value: ModelPassport) -> bool:
    return bool(
        value.passport_revision == 1 and value.predecessor is None
        and value.promotion_status == "candidate"
        and value.conformance_status == "not_run"
        and not value.conformance_evidence and value.rejection_reason is None
    )


def _require_copy_forward(
    candidate: ModelPassport, promoted: ModelPassport, ref: ModelPassportRef,
) -> None:
    predecessor = promoted.predecessor
    if (
        promoted.passport_revision != 2
        or promoted.promotion_status != "promotable"
        or promoted.conformance_status != "passed"
        or predecessor is None
        or predecessor.model_dump() != ref.model_dump()
        or not promoted.conformance_evidence
        or any(item.verifier_identity != native_conformance_identity(
            promoted.inference.loader,
        )[1] for item in promoted.conformance_evidence)
    ):
        raise ValueError("revision two is not a trusted promotion of the candidate")
    left = candidate.model_dump(mode="json", exclude=_ALLOWED_PROMOTION_CHANGES)
    right = promoted.model_dump(mode="json", exclude=_ALLOWED_PROMOTION_CHANGES)
    if left != right:
        raise ValueError("revision two changes immutable candidate bindings")


__all__ = ["ModelPassportService"]
