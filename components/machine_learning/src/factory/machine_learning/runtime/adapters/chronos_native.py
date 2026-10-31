"""Native Chronos-2 artifact persistence and strict local cold inference."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from peft import PeftModel

from ..chronos_acquisition_evidence import validate_acquisition_document
from ..passport_tree_seal import (
    remove_staging_tree, require_read_only_tree, seal_read_only_tree,
)
from ..passport_trees import chronos_native_artifact_ref, chronos_tree_manifest
from .chronos_artifact import load_probe, public_fields
from .chronos_pipeline import load_local_pipeline
from .chronos_scoring import score_chronos_classifier


def passport_config(path: str | Path) -> dict[str, Any]:
    """Re-derive authority only from a recursively sealed native tree."""
    root = Path(path)
    require_read_only_tree(root)
    config = _derive_passport_config(root)
    require_read_only_tree(root)
    return config


def _derive_passport_config(root: Path) -> dict[str, Any]:
    validate_acquisition_document(root / "backbone")
    payload, _ = load_probe(root)
    return {
        **public_fields(payload),
        "artifact_manifest": chronos_tree_manifest(root, root.parent),
    }


def seal_content_addressed(staging: Path, durable_root: Path) -> Path:
    """Validate and publish one complete tree at its immutable digest address."""
    try:
        _derive_passport_config(staging)
        reference = chronos_native_artifact_ref("model", staging, durable_root)
        destination = durable_root / reference.digest
        if destination.exists():
            existing = chronos_native_artifact_ref("model", destination, durable_root)
            passport_config(destination)
            require_read_only_tree(destination)
            if existing.digest != reference.digest:
                raise ValueError("Chronos content-address collision")
            remove_staging_tree(staging)
            return destination
        seal_read_only_tree(staging)
        staging.rename(destination)
        passport_config(destination)
        require_read_only_tree(destination)
        return destination
    except Exception:
        remove_staging_tree(staging)
        raise


def load_scores(
    path: str | Path, expected_config: dict[str, Any], X: np.ndarray,
) -> np.ndarray:
    """Load only sealed local native bytes and return classifier probabilities."""
    root = Path(path)
    actual = passport_config(root)
    if actual != expected_config:
        raise ValueError("Chronos native tree disagrees with passport architecture")
    payload, head = load_probe(root)
    if (
        X.ndim != 3
        or tuple(X.shape[1:]) != (payload["window_size"], payload["input_size"])
        or X.dtype.kind not in "fiu" or not np.isfinite(X).all()
    ):
        raise ValueError("Chronos input shape or values disagree with sealed contract")
    pipeline = load_local_pipeline(root / "backbone")
    base_model = pipeline.inner_model
    if int(base_model.config.d_model) != payload["d_model"]:
        raise ValueError("Chronos local backbone config disagrees with passport")
    encode_model = base_model
    if payload["adapter_mode"] == "lora":
        encode_model = PeftModel.from_pretrained(
            base_model, root / "adapter", is_trainable=False,
            local_files_only=True, autocast_adapter_dtype=False,
        )
        if not isinstance(encode_model, PeftModel):
            raise ValueError("Chronos PEFT loader did not return a native PeftModel")
    else:
        for parameter in base_model.parameters():
            parameter.requires_grad_(False)
    probabilities = score_chronos_classifier(
        encode_model, head, X, payload["scaler_mean"], payload["scaler_scale"],
    )
    if probabilities.shape != (len(X), payload["num_classes"]):
        raise ValueError("Chronos native classifier returned invalid probabilities")
    require_read_only_tree(root)
    return probabilities


__all__ = ["load_scores", "passport_config", "seal_content_addressed"]
