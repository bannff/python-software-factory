"""Strict native MLX metadata, cold loader, and classifier scoring."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from ..mlx_pinned_tree import PinnedMlxTree
from ..mlx_publication import verified_mlx_tree
from ..passport_validation import canonical_json
from ..ports import TimeSeriesModelType
from .mlx_architecture import architecture_spec, build_model
from .mlx_identity import ARTIFACT_FORMAT, BACKEND, FRAMEWORK, LOADER, VERIFIER
from .mlx_native_metadata import decode_metadata
from .mlx_platform import MLX_VERSION, require_mlx_platform

WEIGHTS_FILE, CONFIG_FILE = "model.safetensors", "factory_model.json"


def write_native_tree(
    root: Path, model: Any, model_type: TimeSeriesModelType,
    input_size: int, window_size: int, num_classes: int,
    scaler_mean: np.ndarray, scaler_scale: np.ndarray,
) -> None:
    """Write only public MLX safetensors plus canonical strict metadata."""
    require_mlx_platform()
    revision, constructor = architecture_spec(model_type)
    payload = {
        "schema_version": "1.0", "model_type": model_type.value,
        "architecture_revision": revision, "constructor": constructor,
        "input_size": input_size, "window_size": window_size,
        "num_classes": num_classes, "class_order": list(range(num_classes)),
        "positive_class_index": 1, "threshold": 0.5,
        "scaler_mean": np.asarray(scaler_mean, dtype=np.float64).tolist(),
        "scaler_scale": np.asarray(scaler_scale, dtype=np.float64).tolist(),
        "scaler_dtype": "float64", "scaler_length": input_size,
        "backend": BACKEND, "framework": FRAMEWORK,
        "framework_version": MLX_VERSION, "loader": LOADER,
        "artifact_format": ARTIFACT_FORMAT, "verifier_identity": VERIFIER,
    }
    model.save_weights(str(root / WEIGHTS_FILE))
    config = root / CONFIG_FILE
    with config.open("xb") as stream:
        stream.write(canonical_json(payload)); stream.flush(); os.fsync(stream.fileno())
    _fsync_file(root / WEIGHTS_FILE)


def validate_unsealed_tree(root: str | Path) -> dict[str, Any]:
    """Strictly reload an unsealed private staging tree before publication."""
    path = Path(root)
    payload = _metadata_path(path)
    _load_model_path(path, payload)
    return payload


def validate_pinned_tree(tree: PinnedMlxTree) -> dict[str, Any]:
    """Strictly load metadata and weights only through a pinned object fd."""
    payload = _metadata_pinned(tree)
    _load_model_pinned(tree, payload)
    return payload


def passport_config(root: str | Path) -> dict[str, Any]:
    """Re-derive passport fields from an exact committed MLX reference."""
    with verified_mlx_tree(root) as tree:
        return _passport_config_pinned(tree)


def _passport_config_pinned(tree: PinnedMlxTree) -> dict[str, Any]:
    payload = validate_pinned_tree(tree)
    return {**payload, "artifact_manifest": tree.manifest}


def load_scores(
    root: str | Path, expected_type: str, expected_config: dict[str, Any],
    X: np.ndarray,
) -> np.ndarray:
    """Cold-load exact pinned MLX weights and return classifier probabilities."""
    require_mlx_platform()
    with verified_mlx_tree(root) as tree:
        actual = _passport_config_pinned(tree)
        payload = _metadata_pinned(tree)
        if payload["model_type"] != expected_type or actual != expected_config:
            raise ValueError("MLX native tree disagrees with passport architecture")
        if (
            X.ndim != 3 or tuple(X.shape[1:]) != (
                payload["window_size"], payload["input_size"],
            ) or X.dtype != np.dtype(np.float32) or not np.isfinite(X).all()
        ):
            raise ValueError("MLX input shape, dtype, or values violate sealed contract")
        model = _load_model_pinned(tree, payload)
        mean = np.asarray(payload["scaler_mean"], dtype=np.float64)
        scale = np.asarray(payload["scaler_scale"], dtype=np.float64)
        scaled = ((X.reshape(-1, X.shape[-1]) - mean) / scale).reshape(X.shape)
        import mlx.core as mx
        logits = model(
            mx.array(np.ascontiguousarray(scaled, dtype=np.float32)), training=False,
        )
        scores = np.asarray(mx.softmax(logits, axis=1))
        if scores.shape != (len(X), payload["num_classes"]) or not np.isfinite(scores).all():
            raise ValueError("MLX classifier returned invalid probabilities")
        return scores


def _metadata_path(root: Path) -> dict[str, Any]:
    require_mlx_platform()
    if {item.name for item in root.iterdir()} != {WEIGHTS_FILE, CONFIG_FILE}:
        raise ValueError("MLX native tree must contain exactly two approved files")
    for name in (WEIGHTS_FILE, CONFIG_FILE):
        value = root / name
        if not value.is_file() or value.is_symlink():
            raise ValueError("MLX native tree contains an invalid artifact")
    return decode_metadata((root / CONFIG_FILE).read_bytes())


def _metadata_pinned(tree: PinnedMlxTree) -> dict[str, Any]:
    require_mlx_platform()
    return decode_metadata(tree.read_bytes(CONFIG_FILE))


def _new_model(payload: dict[str, Any]) -> Any:
    return build_model(
        TimeSeriesModelType(payload["model_type"]), payload["input_size"],
        payload["num_classes"],
    )


def _load_model_path(root: Path, payload: dict[str, Any]) -> Any:
    model = _new_model(payload)
    model.load_weights(str(root / WEIGHTS_FILE), strict=True)
    return _finish_model_load(model)


def _load_model_pinned(tree: PinnedMlxTree, payload: dict[str, Any]) -> Any:
    import mlx.core as mx
    model = _new_model(payload)
    with tree.open_file(WEIGHTS_FILE) as descriptor:
        weights = list(mx.load(f"/dev/fd/{descriptor}", format="safetensors").items())
        model.load_weights(weights, strict=True)
    return _finish_model_load(model)


def _finish_model_load(model: Any) -> Any:
    import mlx.core as mx
    from mlx.utils import tree_flatten
    mx.eval(model.parameters())
    if any(not np.isfinite(np.asarray(value)).all() for _, value in tree_flatten(model.parameters())):
        raise ValueError("MLX weights contain non-finite values")
    return model


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "ARTIFACT_FORMAT", "BACKEND", "FRAMEWORK", "LOADER", "VERIFIER",
    "load_scores", "passport_config", "validate_pinned_tree",
    "validate_unsealed_tree", "write_native_tree",
]
