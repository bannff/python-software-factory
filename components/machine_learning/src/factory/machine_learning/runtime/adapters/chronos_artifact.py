"""Strict weights-only Chronos probe and native-tree metadata contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .chronos_identity import (
    EMBEDDING, LIMITATION, MODEL_CLASS, MODEL_ID, MODEL_REVISION, PARITY_TOLERANCE,
    PIPELINE_CLASS, POOLING, PROBE_CLASS, package_versions,
)
from .chronos_probe_head import ChronosProbeHead

_REQUIRED = {
    "schema_version", "probe_state_dict", "model_type", "pipeline_class",
    "model_class", "model_id", "model_revision", "d_model", "embedding",
    "pooling", "probe_class", "probe_constructor", "input_size", "window_size",
    "feature_count", "num_classes", "class_order", "positive_class_index",
    "threshold", "scaler_mean", "scaler_scale", "scaler_dtype", "scaler_length",
    "adapter_mode", "lora_config", "adapter_metadata", "limitations",
    "chronos_version", "peft_version", "torch_version", "transformers_version",
    "parity_tolerance",
}


def save_probe(
    root: Path, head: ChronosProbeHead, *, d_model: int, input_size: int,
    window_size: int, num_classes: int, scaler_mean: np.ndarray,
    scaler_scale: np.ndarray, adapter_mode: str,
    lora_config: dict[str, Any] | None,
) -> None:
    """Persist tensors and exact native identities without pickled modules."""
    probe_dir = root / "probe"
    probe_dir.mkdir()
    adapter_metadata = _adapter_metadata(root, adapter_mode, lora_config)
    constructor = {
        "embedding_dim": d_model, "num_classes": num_classes,
        "hidden_dim": max(d_model // 4, num_classes * 4), "dropout": 0.1,
    }
    torch.save({
        "schema_version": "1.0", "probe_state_dict": head.state_dict(),
        "model_type": "chronos", "pipeline_class": PIPELINE_CLASS,
        "model_class": MODEL_CLASS, "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION, "d_model": d_model,
        "embedding": EMBEDDING, "pooling": POOLING, "probe_class": PROBE_CLASS,
        "probe_constructor": constructor, "input_size": input_size,
        "window_size": window_size, "feature_count": input_size,
        "num_classes": num_classes, "class_order": list(range(num_classes)),
        "positive_class_index": 1, "threshold": 0.5,
        "scaler_mean": torch.from_numpy(np.asarray(scaler_mean, dtype=np.float64)),
        "scaler_scale": torch.from_numpy(np.asarray(scaler_scale, dtype=np.float64)),
        "scaler_dtype": "torch.float64", "scaler_length": input_size,
        "adapter_mode": adapter_mode, "lora_config": lora_config,
        "adapter_metadata": adapter_metadata, "limitations": [LIMITATION],
        "parity_tolerance": dict(PARITY_TOLERANCE), **package_versions(),
    }, probe_dir / "probe.pt")


def load_probe(root: Path) -> tuple[dict[str, Any], ChronosProbeHead]:
    """Load and validate exact keys, tensors, scaler, classes, and identities."""
    try:
        payload = torch.load(root / "probe" / "probe.pt", weights_only=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Chronos probe is unreadable as weights-only data") from exc
    if not isinstance(payload, dict) or set(payload) != _REQUIRED:
        raise ValueError("Chronos probe fields are not exact")
    _validate_identity(payload)
    constructor = payload["probe_constructor"]
    head = ChronosProbeHead(**constructor)
    expected = head.state_dict()
    state = payload["probe_state_dict"]
    if not isinstance(state, dict) or set(state) != set(expected):
        raise ValueError("Chronos probe state keys are not exact")
    for key, tensor in state.items():
        target = expected[key]
        if (
            not isinstance(tensor, torch.Tensor) or tensor.shape != target.shape
            or tensor.dtype != target.dtype or not torch.isfinite(tensor).all()
        ):
            raise ValueError("Chronos probe state shape, dtype, or values are invalid")
    head.load_state_dict(state, strict=True)
    head.eval()
    _validate_scaler(payload)
    expected_metadata = _adapter_metadata(root, payload["adapter_mode"], payload["lora_config"])
    if payload["adapter_metadata"] != expected_metadata:
        raise ValueError("Chronos PEFT metadata disagrees with the probe")
    return payload, head


def public_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return every passport-bound non-weight field, including exact scaler values."""
    fields = {
        key: value for key, value in payload.items()
        if key not in {"probe_state_dict", "scaler_mean", "scaler_scale"}
    }
    fields["scaler_mean"] = payload["scaler_mean"].tolist()
    fields["scaler_scale"] = payload["scaler_scale"].tolist()
    return fields


def _validate_identity(payload: dict[str, Any]) -> None:
    expected = {
        "schema_version": "1.0", "model_type": "chronos",
        "pipeline_class": PIPELINE_CLASS, "model_class": MODEL_CLASS,
        "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
        "embedding": EMBEDDING, "pooling": POOLING, "probe_class": PROBE_CLASS,
        "positive_class_index": 1, "threshold": 0.5,
        "limitations": [LIMITATION], "parity_tolerance": PARITY_TOLERANCE,
        **package_versions(),
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("Chronos native identity or framework version is invalid")
    expected_constructor = {
        "embedding_dim": payload["d_model"],
        "num_classes": payload["num_classes"],
        "hidden_dim": max(payload["d_model"] // 4, payload["num_classes"] * 4),
        "dropout": 0.1,
    }
    if payload["probe_constructor"] != expected_constructor:
        raise ValueError("Chronos probe constructor is not exact")
    dims = (payload["d_model"], payload["input_size"], payload["window_size"], payload["num_classes"])
    if not all(type(value) is int and value > 0 for value in dims):
        raise ValueError("Chronos native dimensions are invalid")
    if (
        payload["feature_count"] != payload["input_size"]
        or payload["num_classes"] < 2
        or payload["class_order"] != list(range(payload["num_classes"]))
        or payload["adapter_mode"] not in {"frozen", "lora"}
        or (payload["adapter_mode"] == "frozen") != (payload["lora_config"] is None)
    ):
        raise ValueError("Chronos classifier or adapter contract is invalid")


def _validate_scaler(payload: dict[str, Any]) -> None:
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
        raise ValueError("Chronos scaler contract is invalid")


def _adapter_metadata(
    root: Path, mode: str, contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    adapter = root / "adapter"
    if mode == "frozen":
        if contract is not None or adapter.exists():
            raise ValueError("Frozen Chronos artifacts must not contain an adapter")
        return None
    try:
        metadata = json.loads((adapter / "adapter_config.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Chronos PEFT metadata is unreadable") from exc
    if not (adapter / "adapter_model.safetensors").is_file() or contract is None:
        raise ValueError("Chronos PEFT native files are incomplete")
    if (
        metadata.get("r") != contract["rank"]
        or metadata.get("lora_alpha") != contract["alpha"]
        or metadata.get("lora_dropout") != contract["dropout"]
        or sorted(metadata.get("target_modules", [])) != sorted(contract["target_modules"])
        or metadata.get("bias") != "none" or metadata.get("task_type") is not None
    ):
        raise ValueError("Chronos PEFT metadata is outside the approved contract")
    return metadata


__all__ = ["load_probe", "public_fields", "save_probe"]
