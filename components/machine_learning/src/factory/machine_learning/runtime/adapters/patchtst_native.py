"""Native Hugging Face persistence and strict local loading for PatchTST."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .patchtst_models import PatchTSTClassifier

_PREPROCESSING = "factory_preprocessing.json"
_CLASS = "transformers.models.patchtst.modeling_patchtst.PatchTSTForClassification"
_CONFIG_KEYS = (
    "activation_function", "attention_dropout", "bias", "channel_attention",
    "channel_consistent_masking", "context_length", "d_model", "distribution_output",
    "do_mask_input", "ff_dropout", "ffn_dim", "head_dropout", "init_std", "loss",
    "mask_type", "mask_value", "norm_eps", "norm_type", "num_attention_heads",
    "num_forecast_mask_patches", "num_hidden_layers", "num_input_channels",
    "num_parallel_samples", "num_targets", "output_range", "patch_length",
    "patch_stride", "path_dropout", "pooling_type", "positional_dropout",
    "positional_encoding_type", "pre_norm", "prediction_length", "problem_type",
    "random_mask_ratio", "scaling", "share_embedding", "share_projection",
    "unmasked_channel_indices", "use_cls_token",
)


def save_native(
    root: Path, model: PatchTSTClassifier, input_size: int, window_size: int,
    num_classes: int, scaler_mean: np.ndarray, scaler_scale: np.ndarray,
) -> str:
    """Write only native safe weights/config plus canonical preprocessing metadata."""
    import transformers
    root.mkdir(parents=True, exist_ok=False)
    model.model.save_pretrained(root, safe_serialization=True)
    config = {key: getattr(model.model.config, key) for key in _CONFIG_KEYS}
    document = {
        "schema_version": "1.0", "model_type": "patchtst",
        "model_class": _CLASS, "transformers_version": transformers.__version__,
        "config": config, "input_size": input_size, "window_size": window_size,
        "num_classes": num_classes, "class_order": list(range(num_classes)),
        "positive_class_index": 1, "threshold": 0.5,
        "scaler_mean": np.asarray(scaler_mean, dtype=np.float64).tolist(),
        "scaler_scale": np.asarray(scaler_scale, dtype=np.float64).tolist(),
        "scaler_dtype": "float64", "scaler_length": input_size,
    }
    (root / _PREPROCESSING).write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
    )
    return str(root)


def passport_config(path: str | Path) -> dict[str, Any]:
    document = _read_preprocessing(Path(path))
    return {key: document[key] for key in (
        "schema_version", "model_type", "model_class", "transformers_version",
        "config", "input_size", "window_size", "num_classes", "class_order",
        "positive_class_index", "threshold", "scaler_dtype", "scaler_length",
    )}


def load_scores(
    path: str | Path, expected_config: dict[str, Any], X: np.ndarray,
) -> np.ndarray:
    """Fail closed on metadata/config/loading-info, then score locally."""
    root = Path(path)
    document = _read_preprocessing(root)
    if passport_config(root) != expected_config:
        raise ValueError("PatchTST preprocessing disagrees with passport architecture")
    if X.ndim != 3 or tuple(X.shape[1:]) != (
        document["window_size"], document["input_size"],
    ):
        raise ValueError("PatchTST input shape disagrees with sealed contract")
    import transformers
    from transformers import PatchTSTForClassification
    transformers.utils.logging.disable_progress_bar()
    loaded = PatchTSTForClassification.from_pretrained(
        root, local_files_only=True, use_safetensors=True, output_loading_info=True,
    )
    model, info = loaded
    rejected = ("error_msgs", "missing_keys", "unexpected_keys", "mismatched_keys")
    if any(info.get(key) for key in rejected):
        raise ValueError("PatchTST loading info is not clean")
    actual_config = {key: getattr(model.config, key) for key in _CONFIG_KEYS}
    if actual_config != document["config"]:
        raise ValueError("PatchTST config disagrees with preprocessing metadata")
    mean = np.asarray(document["scaler_mean"], dtype=np.float64)
    scale = np.asarray(document["scaler_scale"], dtype=np.float64)
    scaled = ((X.reshape(-1, X.shape[-1]) - mean) / scale).reshape(X.shape)
    model.eval()
    with torch.no_grad():
        logits = model(past_values=torch.from_numpy(scaled.astype(np.float32))).prediction_logits
    return torch.softmax(logits, dim=1).numpy()


def _read_preprocessing(root: Path) -> dict[str, Any]:
    import transformers
    from transformers import PatchTSTForClassification
    try:
        document = json.loads((root / _PREPROCESSING).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PatchTST preprocessing metadata is unreadable") from exc
    required = {
        "schema_version", "model_type", "model_class", "transformers_version",
        "config", "input_size", "window_size", "num_classes", "class_order",
        "positive_class_index", "threshold", "scaler_mean", "scaler_scale",
        "scaler_dtype", "scaler_length",
    }
    if set(document) != required:
        raise ValueError("PatchTST preprocessing fields are not exact")
    if (
        document["schema_version"] != "1.0" or document["model_type"] != "patchtst"
        or document["model_class"] != _CLASS
        or f"{PatchTSTForClassification.__module__}.{PatchTSTForClassification.__name__}" != _CLASS
        or document["transformers_version"] != transformers.__version__
        or set(document["config"]) != set(_CONFIG_KEYS)
    ):
        raise ValueError("PatchTST framework identity or config is invalid")
    dimensions = (document["input_size"], document["window_size"], document["num_classes"])
    if not all(type(value) is int and value > 0 for value in dimensions):
        raise ValueError("PatchTST dimensions are invalid")
    if (
        document["config"]["num_input_channels"] != document["input_size"]
        or document["config"]["context_length"] != document["window_size"]
        or document["config"]["num_targets"] != document["num_classes"]
        or document["class_order"] != list(range(document["num_classes"]))
        or document["positive_class_index"] != 1 or document["threshold"] != 0.5
    ):
        raise ValueError("PatchTST classifier contract is invalid")
    mean = np.asarray(document["scaler_mean"])
    scale = np.asarray(document["scaler_scale"])
    if (
        document["scaler_dtype"] != "float64"
        or document["scaler_length"] != document["input_size"]
        or mean.dtype != np.float64 or scale.dtype != np.float64
        or mean.ndim != 1 or scale.ndim != 1 or len(mean) != document["input_size"]
        or len(scale) != document["input_size"] or not np.isfinite(mean).all()
        or not np.isfinite(scale).all() or not (scale > 0).all()
    ):
        raise ValueError("PatchTST scaler contract is invalid")
    return document


__all__ = ["load_scores", "passport_config", "save_native"]
