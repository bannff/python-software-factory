"""Shared trained-object and cold-load scoring for Chronos classifiers."""
from __future__ import annotations

from typing import Any

import numpy as np
import torch

from .chronos_pipeline import encode_batch
from .torch_data import apply_scaler


def score_chronos_classifier(
    model: torch.nn.Module, head: torch.nn.Module, X: np.ndarray,
    scaler_mean: Any, scaler_scale: Any,
) -> np.ndarray:
    """Score raw windows through one native Chronos/probe math path."""
    model.eval()
    head.eval()
    scaled = apply_scaler(X, scaler_mean, scaler_scale)
    with torch.no_grad():
        embeddings = encode_batch(model, scaled.transpose(0, 2, 1), False)
        probabilities = torch.softmax(head(embeddings), dim=1).cpu().numpy()
    if (
        probabilities.ndim != 2 or probabilities.shape[0] != len(X)
        or probabilities.shape[1] < 2 or not np.isfinite(probabilities).all()
    ):
        raise ValueError("Chronos native classifier returned invalid probabilities")
    return probabilities


__all__ = ["score_chronos_classifier"]
