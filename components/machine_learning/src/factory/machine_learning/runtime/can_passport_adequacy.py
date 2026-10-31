"""Model-bound adequacy correspondence and promotion guards."""
from __future__ import annotations

from typing import Iterable

from .can_evaluation_contracts import CanAdequacyBinding
from .can_lifecycle_refs import CanEvalsPointer


def validate_passport_adequacy(
    pointers: tuple[CanEvalsPointer, ...], bindings: tuple[CanAdequacyBinding, ...],
    promotion_status: str, model_id: str, can_id: str | None,
) -> None:
    """Require exact pointer/case correspondence and eligible PASS for promotion."""
    if tuple(binding.pointer for binding in bindings) != pointers:
        raise ValueError("evaluation pointers and adequacy bindings must correspond exactly")
    if bindings and can_id is None:
        raise ValueError("evaluation adequacy requires a CAN legacy binding")
    if any(
        binding.model_id != model_id or binding.case_id != can_id
        for binding in bindings
    ):
        raise ValueError("evaluation adequacy does not bind the passport model and CAN-ID")
    if promotion_status != "promotable" or not pointers:
        return
    if any(
        binding.run_verdict != "PASS" or not binding.run_promotion_eligible
        for binding in bindings
    ):
        raise ValueError("promotable pointer-bound passport requires eligible PASS adequacy")


def require_promotion_adequacy(
    pointers: tuple[CanEvalsPointer, ...], candidate: tuple[CanAdequacyBinding, ...],
    supplied: Iterable[CanAdequacyBinding] = (),
) -> tuple[CanAdequacyBinding, ...]:
    """Fail closed at service/operation boundaries before publication effects."""
    observed = tuple(supplied)
    if pointers and observed != candidate:
        raise ValueError("verified evaluation adequacy changed candidate bindings")
    if not pointers and observed:
        raise ValueError("pointerless passport cannot acquire evaluation adequacy")
    if any(
        item.run_verdict != "PASS" or not item.run_promotion_eligible
        for item in candidate
    ):
        raise ValueError("evaluation adequacy is failing or promotion-ineligible")
    return observed


__all__ = ["require_promotion_adequacy", "validate_passport_adequacy"]
