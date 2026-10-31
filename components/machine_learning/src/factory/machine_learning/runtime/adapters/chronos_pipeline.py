"""Immutable Chronos-2 acquisition, local loading, and embedding extraction."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from .chronos_identity import MODEL_CLASS, MODEL_ID, MODEL_REVISION
from ..authoring_policy import require_authoring


def acquire_training_pipeline() -> "object":
    """Acquire a fresh exact Hub revision for authoring/training only."""
    require_authoring()
    from chronos import Chronos2Pipeline
    pipeline = Chronos2Pipeline.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, device_map="cpu",
    )
    _validate_pipeline(pipeline)
    return pipeline


def save_backbone(pipeline: "object", path: Path) -> None:
    """Persist a complete native safe-serialized local backbone."""
    pipeline.save_pretrained(path, safe_serialization=True)
    required = {"config.json", "model.safetensors"}
    if not required.issubset(child.name for child in path.iterdir()):
        raise ValueError("Chronos native backbone persistence is incomplete")


def load_local_pipeline(path: Path) -> "object":
    """Load a new pipeline strictly from a verified private local snapshot."""
    from chronos import Chronos2Pipeline
    pipeline = Chronos2Pipeline.from_pretrained(
        path, local_files_only=True, use_safetensors=True, device_map="cpu",
    )
    _validate_pipeline(pipeline)
    return pipeline


def encode_batch(
    model: "object", X_batch: np.ndarray, requires_grad: bool,
) -> torch.Tensor:
    """Mean-pool Chronos encoder patches, then channels, for CAN classification."""
    batch, channels, sequence = X_batch.shape
    context = torch.from_numpy(X_batch.reshape(batch * channels, sequence)).float()
    group_ids = torch.arange(batch).repeat_interleave(channels)
    context_manager = torch.enable_grad() if requires_grad else torch.no_grad()
    with context_manager:
        encoder, _loc_scale, *_ = model.encode(
            context=context, group_ids=group_ids, num_output_patches=1,
        )
        return encoder.last_hidden_state.mean(dim=1).reshape(
            batch, channels, -1,
        ).mean(dim=1)


def _validate_pipeline(pipeline: "object") -> None:
    from chronos import Chronos2Pipeline
    if type(pipeline) is not Chronos2Pipeline:
        raise ValueError("Chronos pipeline public class is not exact")
    model = pipeline.inner_model
    model_identity = f"{type(model).__module__}.{type(model).__name__}"
    if model_identity != MODEL_CLASS:
        raise ValueError("Chronos inner model class is not exact")


__all__ = [
    "acquire_training_pipeline", "encode_batch", "load_local_pipeline", "save_backbone",
]
