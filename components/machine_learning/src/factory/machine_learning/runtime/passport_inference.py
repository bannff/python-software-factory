"""Exact-passport authority gate for cold CAN inference."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .passport_composition import create_local_passport_service
from .passport_native_contract import native_conformance_identity
from .passport_service import ModelPassportService
from .passport_snapshot import verified_snapshot
from .passport_store_models import ModelPassportRef

if TYPE_CHECKING:
    from .adapters.can_inference import CanInferenceBridge
    from .runtime import TrackingRuntime


class ModelNotPromotableError(ValueError):
    """The model lacks an exact verified deployable passport."""


def get_exact_inference_bridge(
    runtime: "TrackingRuntime", ref: ModelPassportRef,
) -> "CanInferenceBridge":
    """Cold-load solely from a private snapshot of one exact trusted revision."""
    try:
        service: ModelPassportService = (
            runtime._passport_service or create_local_passport_service()
        )
        passport = service.get(ref)
        root = service.storage_root
        if not root:
            raise ValueError("passport service has no configured durable root")
    except Exception as exc:
        raise ModelNotPromotableError(
            f"exact passport failed retrieval or verification: {exc}"
        ) from exc
    _require_promoted_lightgbm(passport)
    from .adapters.can_inference import CanInferenceBridge
    from .can_feature_contract import load_can_feature_contract
    with verified_snapshot(passport, root, ("model", "feature_contract")) as snapshot:
        contract_uri = snapshot["feature_contract"].as_uri()
        contract = load_can_feature_contract(contract_uri)
        bridge = CanInferenceBridge(
            model_id=passport.model_id, model_path=str(snapshot["model"]),
            model_digest=passport.model_artifact.digest,
            model_type="lightgbm", loader_id="mlflow.lightgbm",
            contract_uri=contract_uri,
            contract_digest=passport.preparation.materializer.config_digest,
            can_id=contract.can_id,
            required_shape=tuple(passport.preparation.contract_shape),
            required_width=passport.preparation.contract_width,
            storage_root=str(snapshot["root"]),
        )
    return bridge


def get_public_inference_bridge(
    runtime: "TrackingRuntime", model_id: str,
) -> "CanInferenceBridge":
    """Non-authoritative warm compatibility path; never selects trust roots."""
    entry = runtime._inference_registry.get(model_id)
    if entry is None:
        raise KeyError(f"Model not registered for inference: {model_id}")
    raw_ref = entry.get("passport_ref")
    if not isinstance(raw_ref, dict):
        raise ModelNotPromotableError("model has no exact registered passport")
    try:
        ref = ModelPassportRef.model_validate(raw_ref)
        service = runtime._passport_service or create_local_passport_service()
        passport = service.get(ref)
    except Exception as exc:
        raise ModelNotPromotableError(
            f"registered passport failed retrieval or verification: {exc}"
        ) from exc
    _require_promoted_lightgbm(passport)
    if not _bindings_match(passport, entry):
        raise ModelNotPromotableError(
            "registered passport bindings disagree with warm inference entry"
        )
    return get_exact_inference_bridge(runtime, ref)


def _require_promoted_lightgbm(passport: Any) -> None:
    if (
        passport.architecture.framework != "lightgbm"
        or passport.inference.adapter != "can_inference"
        or passport.inference.loader != "mlflow.lightgbm"
    ):
        raise ModelNotPromotableError("exact passport has no supported native loader")
    _, verifier = native_conformance_identity(passport.inference.loader)
    if (
        passport.passport_revision != 2
        or passport.promotion_status != "promotable"
        or passport.conformance_status != "passed"
        or not passport.conformance_evidence
        or any(item.verifier_identity != verifier
               for item in passport.conformance_evidence)
    ):
        raise ModelNotPromotableError(
            "exact passport is not trusted revision-2 passed conformance"
        )


def _bindings_match(passport: Any, entry: dict[str, Any]) -> bool:
    preparation, inference = passport.preparation, passport.inference
    return bool(
        passport.model_artifact.digest == entry.get("model_digest")
        and preparation.feature_contract.digest == entry.get("contract_digest")
        and preparation.x.digest == entry.get("prepared_x_digest")
        and preparation.y.digest == entry.get("prepared_y_digest")
        and preparation.materializer.config_digest == entry.get("materializer_config_digest")
        and inference.adapter == entry.get("inference_adapter")
        and inference.loader == entry.get("loader_id")
        and inference.version == entry.get("inference_version")
    )


__all__ = [
    "ModelNotPromotableError", "get_exact_inference_bridge",
    "get_public_inference_bridge",
]
