"""Strict native ``ncps.torch.LTC`` checkpoint and timing lifecycle."""
from __future__ import annotations

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np
import torch
from ncps.torch import LTC

from .lnn_models import LNNClassifier

_REVISION = "factory.ncps.ltc.v1"
_MODEL_CLASS = "ncps.torch.LTC"
_CONSTRUCTOR = {
    "hidden_size": 32, "n_layers": 1, "pool_last": 4, "dropout": 0.1,
}
_REQUIRED = {
    "schema_version", "state_dict", "model_type", "architecture_revision",
    "model_class", "constructor", "input_size", "window_size", "num_classes",
    "class_order", "positive_class_index", "threshold", "scaler_mean",
    "scaler_scale", "scaler_dtype", "scaler_length", "timing_scale",
    "timing_shape", "timing_digest", "timing_dtype", "ncps_version",
    "torch_version",
}


def timing_artifact(
    uri_or_path: str, expected_shape: tuple[int, int],
) -> tuple[np.ndarray, float, str]:
    """Load exact timing bytes and return validated float64 values, scale, digest."""
    path = _path(uri_or_path)
    raw = path.read_bytes()
    try:
        values = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError("LNN timespans artifact is unreadable") from exc
    _validate_timespans(values, expected_shape)
    values64 = np.asarray(values, dtype=np.float64)
    scale = float(values64.mean(dtype=np.float64))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("LNN timespans scale is invalid")
    return values64, scale, hashlib.sha256(raw).hexdigest()


def checkpoint_payload(
    state: dict[str, torch.Tensor], input_size: int, window_size: int,
    num_classes: int, scaler_mean: np.ndarray, scaler_scale: np.ndarray,
    timing_scale: float, timing_shape: tuple[int, int], timing_digest: str,
) -> dict[str, Any]:
    """Create the complete weights-only native LTC artifact contract."""
    return {
        "schema_version": "1.0", "state_dict": state, "model_type": "lnn",
        "architecture_revision": _REVISION, "model_class": _MODEL_CLASS,
        "constructor": dict(_CONSTRUCTOR), "input_size": input_size,
        "window_size": window_size, "num_classes": num_classes,
        "class_order": list(range(num_classes)), "positive_class_index": 1,
        "threshold": 0.5,
        "scaler_mean": torch.from_numpy(np.asarray(scaler_mean, dtype=np.float64)),
        "scaler_scale": torch.from_numpy(np.asarray(scaler_scale, dtype=np.float64)),
        "scaler_dtype": "torch.float64", "scaler_length": input_size,
        "timing_scale": timing_scale, "timing_shape": list(timing_shape),
        "timing_digest": timing_digest, "timing_dtype": "float64",
        "ncps_version": version("ncps"), "torch_version": str(torch.__version__),
    }


def passport_config(path: str | Path) -> dict[str, Any]:
    """Validate an LTC artifact and expose its exact sealed passport fields."""
    payload = torch.load(path, weights_only=True)
    _validate(payload)
    return {key: payload[key] for key in (
        "schema_version", "model_type", "architecture_revision", "model_class",
        "constructor", "input_size", "window_size", "num_classes", "class_order",
        "positive_class_index", "threshold", "scaler_dtype", "scaler_length",
        "timing_scale", "timing_shape", "timing_digest", "timing_dtype",
        "ncps_version", "torch_version",
    )}


def load_scores(
    path: str | Path, expected_config: dict[str, Any], X: np.ndarray,
    timespans: np.ndarray,
) -> np.ndarray:
    """Strictly reconstruct native LTC state and score with mandatory timing."""
    payload = torch.load(path, weights_only=True)
    _validate(payload)
    if passport_config(path) != expected_config:
        raise ValueError("LNN checkpoint disagrees with passport architecture")
    expected_x = (payload["window_size"], payload["input_size"])
    if X.ndim != 3 or tuple(X.shape[1:]) != expected_x:
        raise ValueError("LNN input shape disagrees with sealed contract")
    if X.dtype.kind not in "fiu" or not np.isfinite(X).all():
        raise ValueError("LNN input must be finite numeric data")
    _validate_timespans(timespans, (len(X), payload["window_size"]))
    model = _build(payload)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    mean = payload["scaler_mean"].numpy()
    scale = payload["scaler_scale"].numpy()
    scaled = ((X.reshape(-1, X.shape[-1]) - mean) / scale).reshape(X.shape)
    normalized = np.asarray(timespans, dtype=np.float64) / payload["timing_scale"]
    with torch.no_grad():
        logits = model(
            torch.from_numpy(scaled.astype(np.float32)),
            torch.from_numpy(normalized.astype(np.float32)),
        )
        return torch.softmax(logits, dim=1).numpy()


def _validate(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != _REQUIRED:
        raise ValueError("LNN checkpoint fields are not exact")
    if (
        payload["schema_version"] != "1.0" or payload["model_type"] != "lnn"
        or payload["architecture_revision"] != _REVISION
        or payload["model_class"] != _MODEL_CLASS
        or f"{LTC.__module__.removesuffix('.ltc')}.{LTC.__name__}" != _MODEL_CLASS
        or payload["constructor"] != _CONSTRUCTOR
        or payload["ncps_version"] != version("ncps")
        or payload["torch_version"] != str(torch.__version__)
    ):
        raise ValueError("LNN framework or constructor identity is invalid")
    dimensions = (payload["input_size"], payload["window_size"], payload["num_classes"])
    if not all(type(value) is int and value > 0 for value in dimensions):
        raise ValueError("LNN dimensions are invalid")
    classes = payload["num_classes"]
    if (
        classes < 2 or payload["class_order"] != list(range(classes))
        or payload["positive_class_index"] != 1 or payload["threshold"] != 0.5
    ):
        raise ValueError("LNN classifier contract is invalid")
    mean, scale = payload["scaler_mean"], payload["scaler_scale"]
    if (
        payload["scaler_dtype"] != "torch.float64"
        or payload["scaler_length"] != payload["input_size"]
        or not isinstance(mean, torch.Tensor) or not isinstance(scale, torch.Tensor)
        or mean.dtype != torch.float64 or scale.dtype != torch.float64
        or mean.shape != scale.shape or mean.numel() != payload["input_size"]
        or not torch.isfinite(mean).all() or not torch.isfinite(scale).all()
        or not torch.all(scale > 0)
    ):
        raise ValueError("LNN scaler contract is invalid")
    timing_shape = payload["timing_shape"]
    if (
        type(payload["timing_scale"]) is not float
        or not np.isfinite(payload["timing_scale"]) or payload["timing_scale"] <= 0
        or not isinstance(timing_shape, list) or len(timing_shape) != 2
        or not all(type(value) is int and value > 0 for value in timing_shape)
        or timing_shape[1] != payload["window_size"]
        or payload["timing_dtype"] != "float64"
        or not isinstance(payload["timing_digest"], str)
        or len(payload["timing_digest"]) != 64
        or not isinstance(payload["state_dict"], dict)
    ):
        raise ValueError("LNN timing or state contract is invalid")


def _validate_timespans(values: np.ndarray, expected_shape: tuple[int, int]) -> None:
    if (
        not isinstance(values, np.ndarray) or values.shape != expected_shape
        or values.dtype.kind not in "fiu" or not np.isfinite(values).all()
        or not (values > 0).all()
    ):
        raise ValueError("LNN timespans must be finite positive numeric data of exact shape")


def _build(payload: dict[str, Any]) -> LNNClassifier:
    return LNNClassifier(
        input_size=payload["input_size"], num_classes=payload["num_classes"],
        **payload["constructor"],
    )


def _path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in {"", "file"}:
        raise ValueError("LNN timespans require a local file URI")
    return Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(value)


__all__ = ["checkpoint_payload", "load_scores", "passport_config", "timing_artifact"]
