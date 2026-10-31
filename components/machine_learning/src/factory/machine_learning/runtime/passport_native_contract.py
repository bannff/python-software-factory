"""Shared strict contracts for native neural passport scoring."""
from __future__ import annotations

import numpy as np

from .model_passport import ModelPassport

LNN_LOADER = "ncps.torch.LTC.state_dict"
MLX_LOADER = "mlx.nn.Module.load_weights"


def native_conformance_identity(loader: str) -> tuple[str, str]:
    """Return the one trusted native family and verifier for ``loader``."""
    if loader == "mlflow.lightgbm":
        return "lightgbm", "local-lightgbm-isolated-v1"
    if loader == MLX_LOADER:
        return "mlx", "local-mlx-isolated-v1"
    if loader == "torch.state_dict":
        return "torch", "local-torch-isolated-v1"
    if loader == LNN_LOADER:
        return "lnn", "local-ncps-ltc-isolated-v1"
    if loader == "transformers.patchtst":
        return "patchtst", "local-patchtst-isolated-v1"
    if loader == "chronos.Chronos2Pipeline":
        return "chronos2", "local-chronos2-isolated-v1"
    raise ValueError("native passport loader is not approved")


def require_promoted(passport: ModelPassport) -> None:
    """Require exact revision-two evidence for the selected native loader."""
    try:
        _, expected = native_conformance_identity(passport.inference.loader)
    except ValueError:
        expected = None
    if (
        passport.passport_revision != 2
        or passport.promotion_status != "promotable"
        or passport.conformance_status != "passed"
        or not passport.conformance_evidence
        or expected is None
        or any(item.verifier_identity != expected for item in passport.conformance_evidence)
    ):
        raise ValueError("neural cold scoring requires trusted revision-two conformance")


def validate_contract(
    passport: ModelPassport, config: dict, X: np.ndarray,
) -> None:
    """Validate shared prepared-array, scaler, and classifier bindings."""
    preparation = passport.preparation
    lnn = passport.inference.loader == LNN_LOADER
    timing_shape = preparation.timespans_shape
    if (
        passport.inference.adapter != "can_inference"
        or X.ndim != 3 or X.dtype.kind not in "fiu" or not np.isfinite(X).all()
        or preparation.x_layout != "time_features_3d"
        or len(preparation.x_shape) != 3
        or tuple(preparation.x_shape[1:]) != tuple(X.shape[1:])
        or tuple(preparation.contract_shape) != (
            config.get("window_size"), config.get("input_size"),
        )
        or tuple(X.shape[1:]) != (
            config.get("window_size"), config.get("input_size"),
        )
        or config.get("num_classes") != len(config.get("class_order", []))
        or config.get("positive_class_index") != 1
        or config.get("threshold") != 0.5
        or (lnn and (
            preparation.timespans is None
            or timing_shape != tuple(config.get("timing_shape", ()))
            or timing_shape != (preparation.x_shape[0], config.get("window_size"))
            or config.get("timing_digest") != preparation.timespans.digest
        ))
        or (not lnn and (preparation.timespans is not None or timing_shape is not None))
    ):
        raise ValueError("neural passport input or classifier contract is invalid")


__all__ = [
    "LNN_LOADER", "MLX_LOADER", "native_conformance_identity",
    "require_promoted", "validate_contract",
]
