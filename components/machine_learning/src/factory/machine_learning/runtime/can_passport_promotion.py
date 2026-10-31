"""Rich Evals-gated CAN passport promotion operation."""
from __future__ import annotations

from typing import Any

from .can_evals_binding import verify_evaluation_records
from .can_lifecycle_canonical import CONFORM_OPERATION
from .can_passport_adequacy import require_promotion_adequacy
from .passport_store_models import ModelPassportRef
from .passport_service import ModelPassportService


def promote_passports(
    context: Any, *, conformance_receipt_refs: list[dict[str, Any]], invoker: Any,
    service: ModelPassportService,
) -> dict[str, Any]:
    """Reject unverified, failing, or ineligible adequacy before effects."""
    records = []
    for receipt_ref in conformance_receipt_refs:
        intent, receipt = context.conformance_receipt(receipt_ref, CONFORM_OPERATION)
        value = receipt.output
        ref = ModelPassportRef.model_validate(value.get("passport_ref"))
        receipt_evidence = value.get("conformance_evidence")
        if not isinstance(receipt_evidence, dict):
            raise ValueError("conformance receipt evidence is malformed")
        candidate = service.get(ref)
        verified = verify_evaluation_records(invoker, candidate.evaluation_pointers)
        pointers = tuple(item.pointer for item in verified)
        can_id = _can_id(candidate)
        bindings = tuple(
            item.binding_for(candidate.model_id, can_id) for item in verified
        )
        require_promotion_adequacy(
            candidate.evaluation_pointers, candidate.evaluation_adequacy, bindings,
        )
        canonical_pointers = [item.model_dump(mode="json") for item in pointers]
        if (
            intent.unit != f"conformance:{ref.digest}@v1"
            or intent.inputs != {
                "passport_ref": ref.model_dump(mode="json"),
                "evaluation_pointers": canonical_pointers,
            }
        ):
            raise ValueError("conformance receipt bindings disagree")

        def publish(_effect_id: str) -> dict[str, Any]:
            publication = service.promote_lifecycle(
                ref, receipt_evidence, effect_id=intent.effect_id,
                evaluation_pointers=pointers, evaluation_adequacy=bindings,
            )
            return {
                "can_id": _can_id(candidate),
                "passport_ref": publication.ref.model_dump(mode="json"),
            }

        records.append(context.effect(
            f"promote:{ref.digest}@v1",
            {"conformance_receipt_ref": receipt_ref}, publish, publish,
        ))
    return {
        "can_ids": [item["can_id"] for item in records],
        "passport_refs": [item["passport_ref"] for item in records],
        "passports": records,
    }


def _can_id(passport: Any) -> str:
    binding = passport.can_legacy_binding
    if binding is None:
        raise ValueError("lifecycle passport lacks a CAN legacy binding")
    return binding.can_id


__all__ = ["promote_passports"]
