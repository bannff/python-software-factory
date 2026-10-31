"""Sealed native checkpoint lifecycle for the CAN LSTM and TCN modules."""
from __future__ import annotations

from typing import Any

import numpy as np
import torch

from ..ports import TimeSeriesModelType
from .torch_models import LSTMClassifier, TCNClassifier

_LSTM_REVISION = "factory.lstm.v1"
_TCN_REVISION = "factory.tcn.v1"
_LSTM_CONSTRUCTOR = {"hidden_size": 64, "num_layers": 2, "dropout": 0.1}
_TCN_CONSTRUCTOR = {
    "num_channels": [32, 32, 64], "kernel_size": 3, "dropout": 0.1,
}
_REQUIRED = {
    "schema_version", "state_dict", "model_type", "architecture_revision",
    "constructor", "input_size", "window_size", "num_classes", "class_order",
    "positive_class_index", "threshold", "scaler_mean", "scaler_scale",
    "scaler_dtype", "scaler_length", "torch_version",
}


def checkpoint_payload(
    model_type: TimeSeriesModelType, state: dict[str, torch.Tensor],
    input_size: int, window_size: int, num_classes: int,
    scaler_mean: np.ndarray, scaler_scale: np.ndarray,
) -> dict[str, Any]:
    """Create the complete weights-only artifact contract."""
    revision, constructor = _architecture(model_type)
    return {
        "schema_version": "1.0", "state_dict": state,
        "model_type": model_type.value, "architecture_revision": revision,
        "constructor": constructor, "input_size": input_size,
        "window_size": window_size, "num_classes": num_classes,
        "class_order": list(range(num_classes)), "positive_class_index": 1,
        "threshold": 0.5,
        "scaler_mean": torch.from_numpy(np.asarray(scaler_mean, dtype=np.float64)),
        "scaler_scale": torch.from_numpy(np.asarray(scaler_scale, dtype=np.float64)),
        "scaler_dtype": "torch.float64", "scaler_length": input_size,
        "torch_version": str(torch.__version__),
    }


def passport_config(path: str) -> dict[str, Any]:
    """Read and validate the artifact, then expose its sealed passport fields."""
    payload = torch.load(path, weights_only=True)
    _validate(payload)
    return {
        key: payload[key] for key in (
            "schema_version", "architecture_revision", "constructor", "input_size",
            "window_size", "num_classes", "class_order", "positive_class_index",
            "threshold", "scaler_dtype", "scaler_length", "torch_version",
        )
    }


def load_scores(
    path: str, expected_type: str, expected_config: dict[str, Any], X: np.ndarray,
) -> np.ndarray:
    """Strictly reconstruct from sealed values and return class probabilities."""
    payload = torch.load(path, weights_only=True)
    _validate(payload)
    actual = passport_config(path)
    if payload["model_type"] != expected_type or actual != expected_config:
        raise ValueError("torch checkpoint disagrees with passport architecture")
    if X.ndim != 3 or tuple(X.shape[1:]) != (
        payload["window_size"], payload["input_size"],
    ):
        raise ValueError("torch input shape disagrees with sealed contract")
    model = _build(payload)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    mean = payload["scaler_mean"].numpy()
    scale = payload["scaler_scale"].numpy()
    scaled = ((X.reshape(-1, X.shape[-1]) - mean) / scale).reshape(X.shape)
    with torch.no_grad():
        return torch.softmax(model(torch.from_numpy(scaled.astype(np.float32))), dim=1).numpy()


def _validate(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != _REQUIRED:
        raise ValueError("torch checkpoint fields are not exact")
    if payload["schema_version"] != "1.0" or payload["torch_version"] != str(torch.__version__):
        raise ValueError("torch checkpoint framework version is not exact")
    model_type = TimeSeriesModelType(payload["model_type"])
    revision, constructor = _architecture(model_type)
    if payload["architecture_revision"] != revision or payload["constructor"] != constructor:
        raise ValueError("torch architecture revision or constructor is invalid")
    input_size, window_size, classes = (
        payload["input_size"], payload["window_size"], payload["num_classes"],
    )
    if not all(type(value) is int and value > 0 for value in (input_size, window_size, classes)):
        raise ValueError("torch checkpoint dimensions are invalid")
    if (
        classes < 2 or payload["class_order"] != list(range(classes))
        or payload["positive_class_index"] != 1 or payload["threshold"] != 0.5
    ):
        raise ValueError("torch classifier contract is invalid")
    mean, scale = payload["scaler_mean"], payload["scaler_scale"]
    if (
        payload["scaler_dtype"] != "torch.float64"
        or payload["scaler_length"] != input_size
        or not isinstance(mean, torch.Tensor) or not isinstance(scale, torch.Tensor)
        or mean.dtype != torch.float64 or scale.dtype != torch.float64
        or mean.ndim != 1 or scale.ndim != 1
        or mean.numel() != input_size or scale.numel() != input_size
        or not torch.isfinite(mean).all() or not torch.isfinite(scale).all()
        or not torch.all(scale > 0)
    ):
        raise ValueError("torch scaler contract is invalid")
    if not isinstance(payload["state_dict"], dict):
        raise ValueError("torch state_dict is invalid")


def _architecture(model_type: TimeSeriesModelType) -> tuple[str, dict[str, Any]]:
    if model_type is TimeSeriesModelType.lstm:
        return _LSTM_REVISION, dict(_LSTM_CONSTRUCTOR)
    if model_type is TimeSeriesModelType.tcn:
        return _TCN_REVISION, dict(_TCN_CONSTRUCTOR)
    raise ValueError("native torch passport supports only LSTM or TCN")


def _build(payload: dict[str, Any]) -> torch.nn.Module:
    config = payload["constructor"]
    if payload["model_type"] == "lstm":
        return LSTMClassifier(
            input_size=payload["input_size"], hidden_size=config["hidden_size"],
            num_layers=config["num_layers"], num_classes=payload["num_classes"],
            dropout=config["dropout"],
        )
    return TCNClassifier(
        input_size=payload["input_size"], num_channels=config["num_channels"],
        kernel_size=config["kernel_size"], num_classes=payload["num_classes"],
        dropout=config["dropout"],
    )


__all__ = ["checkpoint_payload", "load_scores", "passport_config"]
