"""Legacy CAN result projection from promoted ModelPassport authority."""
from __future__ import annotations

from typing import Any

from .can_inference_gate import build_inference_gate
from .can_lifecycle_results import CanProjectResult
from .can_projection_validation import require_training_bindings
from .passport_native_contract import require_promoted
from .passport_store_models import ModelPassportRef

_STAGE_KEYS = (
    "ingest", "profile", "contract_artifacts", "synthesize", "window", "augment",
)
_OPTIONAL_STAGE_KEYS = ("context", "context_artifacts")


def project_pipeline_result(
    *, training_terminal: dict[str, Any], promotion_terminal: dict[str, Any],
    service: Any,
) -> dict[str, Any]:
    """Reconstruct the full legacy result from exact promoted passports only."""
    if promotion_terminal.get("status") != "completed":
        raise ValueError("pipeline projection requires completed promotion")
    refs = promotion_terminal.get("passport_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("promotion terminal has no passport references")
    loaded = []
    for value in refs:
        ref = ModelPassportRef.model_validate(value)
        passport = service.get(ref)
        require_promoted(passport)
        binding = passport.can_legacy_binding
        if binding is None:
            raise ValueError("promoted lifecycle passport lacks CAN legacy binding")
        loaded.append((binding, ref, passport))
    loaded.sort(key=lambda item: item[0].rank)
    _require_agreement(loaded)
    require_training_bindings(training_terminal, loaded)
    table = [_row(binding, ref, passport) for binding, ref, passport in loaded]
    model_ids = [passport.model_id for _, _, passport in loaded]
    projection = loaded[0][0].dataset_projection.model_dump(
        mode="json", exclude_none=True,
    )
    result = {
        "vehicle_id": loaded[0][0].vehicle_id,
        **{key: projection[key] for key in _STAGE_KEYS},
        "top_can_ids": [binding.can_id for binding, _, _ in loaded],
        "comparison_table": table, "model_ids": model_ids,
        "deployable_model_ids": model_ids, "warm_model_ids": [],
        "inference_gate": build_inference_gate(table, []),
    }
    result.update({key: projection[key] for key in _OPTIONAL_STAGE_KEYS if key in projection})
    return CanProjectResult.model_validate(result).model_dump(
        mode="json", exclude_none=True,
    )


def _row(binding, ref, passport) -> dict[str, Any]:
    contract, model = passport.preparation.feature_contract, passport.model_artifact
    return {
        "rank": binding.rank, "can_id": binding.can_id,
        "model_id": passport.model_id, "model_version": passport.model_version,
        "model_type": passport.architecture.architecture,
        "n_windows": binding.n_windows, "n_features": binding.n_features,
        "window_size": binding.window_size, "label_dist": binding.label_dist,
        "metrics": passport.final_metrics, "model_path": model.uri,
        "model_digest": model.digest, "contract_uri": contract.uri,
        "contract_digest": contract.digest,
        "passport_ref": ref.model_dump(mode="json"),
        "passport_digest": passport.passport_digest,
        "passport_revision": passport.passport_revision,
        "passport_status": "published",
        "promotion_status": passport.promotion_status,
        "conformance_status": passport.conformance_status,
        "inference_gate": "passed", "inference_registered": False,
        "registration_status": "promotable",
    }


def _require_agreement(loaded: list[tuple[Any, Any, Any]]) -> None:
    first = loaded[0][0]
    ranks, can_ids = set(), set()
    for binding, _, passport in loaded:
        if (
            binding.vehicle_id != first.vehicle_id
            or binding.dataset_projection != first.dataset_projection
            or passport.evaluation_pointers != loaded[0][2].evaluation_pointers
        ):
            raise ValueError("promoted lifecycle passport bindings disagree")
        if binding.rank in ranks or binding.can_id in can_ids:
            raise ValueError("promoted lifecycle passport ranks/CAN-IDs are not unique")
        ranks.add(binding.rank); can_ids.add(binding.can_id)


__all__ = ["project_pipeline_result"]
