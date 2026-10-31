"""Exact warm LightGBM/joblib model-to-contract bindings and cache."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import TrackingRuntime
    from .adapters.can_inference import CanInferenceBridge


def register_inference_model(
    runtime: "TrackingRuntime", model_id: str, model_path: str, *, can_id: str,
    contract_uri: str, contract_digest: str, model_type: str, loader_id: str,
    model_digest: str, threshold: float, required_shape: tuple[int, int],
    required_width: int, passport_ref: dict[str, Any] | None = None,
    passport_root: str | None = None, prepared_x_digest: str | None = None,
    prepared_y_digest: str | None = None,
    materializer_config_digest: str | None = None,
    inference_adapter: str | None = None, inference_version: str | None = None,
) -> None:
    """Register only the supported warm family and immutable artifact identity."""
    if model_type != "lightgbm" or loader_id not in {"joblib", "mlflow.lightgbm"}:
        raise ValueError(
            "warm CAN inference supports only LightGBM/joblib compatibility "
            "or MLflow native flavor"
        )
    path = Path(model_path)
    if loader_id == "joblib" and path.suffix != ".joblib":
        raise ValueError("legacy LightGBM warm artifact must be a .joblib file")
    if loader_id == "mlflow.lightgbm" and not path.is_dir():
        raise ValueError("MLflow LightGBM warm artifact must be a flavor directory")
    _require_digest(model_digest, "model")
    _require_digest(contract_digest, "contract")
    shape = tuple(required_shape)
    if len(shape) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in shape):
        raise ValueError("required_shape must contain two positive integers")
    if required_width != shape[0] * shape[1]:
        raise ValueError("required_width must equal the flattened contract shape")
    runtime._inference_registry[model_id] = {
        "model_path": str(model_path), "model_digest": model_digest,
        "model_type": model_type, "loader_id": loader_id, "can_id": can_id,
        "contract_uri": contract_uri, "contract_digest": contract_digest,
        "threshold": float(threshold), "required_shape": shape,
        "required_width": int(required_width),
        "passport_ref": passport_ref, "passport_root": passport_root,
        "prepared_x_digest": prepared_x_digest,
        "prepared_y_digest": prepared_y_digest,
        "materializer_config_digest": materializer_config_digest,
        "inference_adapter": inference_adapter,
        "inference_version": inference_version,
    }
    runtime._inference_bridges = {
        key: value for key, value in runtime._inference_bridges.items()
        if not (isinstance(key, tuple) and key[0] == model_id)
    }


def get_inference_bridge(runtime: "TrackingRuntime", model_id: str) -> "CanInferenceBridge":
    entry = runtime._inference_registry.get(model_id)
    if entry is None:
        raise KeyError(f"Model not registered for inference: {model_id}")
    key = (model_id, entry["contract_digest"], entry["model_digest"])
    bridge = runtime._inference_bridges.get(key)
    if bridge is None:
        from .adapters.can_inference import CanInferenceBridge
        bridge_fields = {
            key: entry[key] for key in (
                "model_path", "model_digest", "model_type", "loader_id", "can_id",
                "contract_uri", "contract_digest", "threshold", "required_shape",
                "required_width", "passport_root",
            )
        }
        bridge_fields["storage_root"] = bridge_fields.pop("passport_root")
        bridge = CanInferenceBridge(model_id=model_id, **bridge_fields)
        runtime._inference_bridges[key] = bridge
    return bridge


def get_inference_model_info(
    runtime: "TrackingRuntime", model_id: str,
) -> dict[str, Any] | None:
    entry = runtime._inference_registry.get(model_id)
    if entry is None:
        return None
    info = {
        "model_id": model_id, **entry,
        "required_shape": list(entry["required_shape"]),
    }
    try:
        bridge = get_inference_bridge(runtime, model_id)
    except Exception as exc:
        info["load_error"] = str(exc)
        return info
    importances = getattr(bridge._model, "feature_importances_", None)
    if importances is None:
        return info
    from .adapters.can_inference import _model_columns
    columns = _model_columns(bridge.contract, entry["required_width"])
    if len(importances) != len(columns):
        info["load_error"] = "feature_importances width disagrees with binding"
        return info
    pairs = sorted(zip(columns, map(float, importances)), key=lambda pair: pair[1], reverse=True)
    info["feature_importances"] = [
        {"signal": name, "importance": round(value, 6)} for name, value in pairs
    ]
    return info


def _require_digest(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} digest must be lowercase SHA-256")


__all__ = [
    "get_inference_bridge", "get_inference_model_info", "register_inference_model",
]
