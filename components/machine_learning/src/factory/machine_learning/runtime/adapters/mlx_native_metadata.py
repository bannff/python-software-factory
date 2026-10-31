"""Canonical MLX native metadata decoding and semantic validation."""
from __future__ import annotations

import json
import math
from typing import Any

from ..passport_validation import canonical_json
from ..ports import TimeSeriesModelType
from .mlx_architecture import architecture_spec
from .mlx_identity import ARTIFACT_FORMAT, BACKEND, FRAMEWORK, LOADER, VERIFIER
from .mlx_platform import MLX_VERSION

_REQUIRED = {
    "schema_version", "model_type", "architecture_revision", "constructor",
    "input_size", "window_size", "num_classes", "class_order",
    "positive_class_index", "threshold", "scaler_mean", "scaler_scale",
    "scaler_dtype", "scaler_length", "backend", "framework",
    "framework_version", "loader", "artifact_format", "verifier_identity",
}


def decode_metadata(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("MLX factory metadata is unreadable") from exc
    if not isinstance(payload, dict) or set(payload) != _REQUIRED:
        raise ValueError("MLX factory metadata fields are not exact")
    if raw != canonical_json(payload):
        raise ValueError("MLX factory metadata is not canonical JSON")
    _validate_metadata(payload)
    return payload


def _validate_metadata(payload: dict[str, Any]) -> None:
    identity = {
        "schema_version": "1.0", "backend": BACKEND, "framework": FRAMEWORK,
        "framework_version": MLX_VERSION, "loader": LOADER,
        "artifact_format": ARTIFACT_FORMAT, "verifier_identity": VERIFIER,
        "positive_class_index": 1, "threshold": 0.5, "scaler_dtype": "float64",
    }
    if any(payload.get(key) != value for key, value in identity.items()):
        raise ValueError("MLX lifecycle identity or framework version is invalid")
    try:
        model_type = TimeSeriesModelType(payload["model_type"])
        revision, constructor = architecture_spec(model_type)
    except (ValueError, NotImplementedError) as exc:
        raise ValueError("MLX model family is not approved") from exc
    if payload["architecture_revision"] != revision or payload["constructor"] != constructor:
        raise ValueError("MLX architecture revision or constructor is invalid")
    dims = (payload["input_size"], payload["window_size"], payload["num_classes"])
    if not all(type(value) is int and value > 0 for value in dims):
        raise ValueError("MLX dimensions are invalid")
    classes = payload["num_classes"]
    if classes < 2 or payload["class_order"] != list(range(classes)):
        raise ValueError("MLX classifier classes are invalid")
    mean, scale = payload["scaler_mean"], payload["scaler_scale"]
    valid_number = lambda value: type(value) in {int, float} and math.isfinite(value)
    if (
        payload["scaler_length"] != payload["input_size"]
        or not isinstance(mean, list) or not isinstance(scale, list)
        or len(mean) != payload["input_size"] or len(scale) != len(mean)
        or not all(valid_number(value) for value in (*mean, *scale))
        or not all(value > 0 for value in scale)
    ):
        raise ValueError("MLX scaler contract is invalid")


__all__ = ["decode_metadata"]
