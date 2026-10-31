"""Shared training/persistence helper for transformer-style time-series
adapters (PatchTST, Chronos, LNN).

Both PatchTST and Chronos share the same data prep, scaler, train loop,
and persistence pattern — only the model architecture differs. The
helper exposes a single :func:`train_classifier` function that takes a
model factory and does the rest, so each adapter file can stay under
the 200-LOC ceiling.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ..ports import TimeSeriesModelType, TimeSeriesTrainingConfig, TimeSeriesTrainingJob
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics
from .torch_data import apply_scaler, fit_scaler_transform, load_array, to_windows

_logger = logging.getLogger(__name__)


def _train_loop(
    model: nn.Module, loader: DataLoader,
    X_val: torch.Tensor, y_val: torch.Tensor,
    optimizer: optim.Optimizer, epochs: int, patience: int, grad_clip: float = 1.0,
) -> dict[str, torch.Tensor]:
    """Train with early stopping; return the best-observed state dict.

    ``grad_clip`` is exposed so the LTC adapter can use a tighter
    value (0.5) — LTC recurrent state is shared across timesteps and
    a single bad gradient compounds through the loop.
    """
    criterion = nn.CrossEntropyLoss()
    best_val, best_state, no_improve = float("inf"), None, 0
    for _ in range(epochs):
        model.train()
        for xb, yb in loader:
            optimizer.zero_grad()
            criterion(model(xb), yb).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(X_val), y_val).item()
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    return best_state or {k: v.detach().clone() for k, v in model.state_dict().items()}


def train_classifier(
    model_type: TimeSeriesModelType,
    build_model_fn: Callable[[int, int, int], nn.Module],
    X_uri: str, y_uri: str,
    config: TimeSeriesTrainingConfig,
    model_dir_prefix: str,
    grad_clip: float = 1.0,
) -> tuple[TimeSeriesTrainingJob, str, dict[str, Any], dict[str, Any]]:
    """Train a classifier end-to-end and return ``(job, model_path, payload, record)``.

    Args:
        model_type: Enum value identifying the architecture.
        build_model_fn: Callable ``(input_size, window_size, num_classes) -> nn.Module``.
        X_uri: URI of the windowed feature matrix.
        y_uri: URI of the aligned label array.
        config: Training configuration.
        model_dir_prefix: Directory prefix for the model root
            (e.g. ``"patchtst_ts_"``).
        grad_clip: max-norm for gradient clipping (LTC uses 0.5).

    Returns:
        A 4-tuple ``(job, model_path, payload, record)`` where ``payload``
        is the checkpoint dict and ``record`` is the in-memory registry
        entry. The caller is responsible for persisting the payload
        and registering the record.
    """
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    X = to_windows(load_array(X_uri), config.window_size).astype(np.float32)
    y = load_array(y_uri).ravel().astype(np.int64)
    n_samples, _, n_features = X.shape
    if n_samples != len(y):
        raise ValueError(f"X has {n_samples} windows but y has {len(y)} labels")
    n_classes = max(int(y.max()) + 1, 2)
    Xt, yt, Xv, yv = temporal_split_with_shuffle_fallback(
        X, y, config.validation_split, config.seed,
    )
    Xt, scaler_mean, scaler_scale = fit_scaler_transform(Xt, len(Xt))
    Xv = apply_scaler(Xv, scaler_mean, scaler_scale)
    model = build_model_fn(n_features, config.window_size, n_classes)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xt), torch.from_numpy(yt)),
        batch_size=config.batch_size, shuffle=True,
    )
    best_state = _train_loop(
        model, loader, torch.from_numpy(Xv), torch.from_numpy(yv),
        optim.Adam(model.parameters(), lr=config.learning_rate),
        config.epochs, config.early_stopping_patience, grad_clip=grad_clip,
    )
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        probs = torch.softmax(model(torch.from_numpy(Xv)), dim=1).numpy()
    y_pred, y_score = probs.argmax(axis=1), (probs[:, 1] if probs.shape[1] > 1 else probs[:, 0])
    metrics = compute_classification_metrics(yv, y_pred, y_score)
    job_id = str(uuid.uuid4())
    payload = {
        "state_dict": best_state, "model_type": model_type.value,
        "input_size": n_features, "num_classes": n_classes,
        "window_size": config.window_size,
        "scaler_mean": torch.from_numpy(np.asarray(scaler_mean, dtype=np.float64)),
        "scaler_scale": torch.from_numpy(np.asarray(scaler_scale, dtype=np.float64)),
    }
    record = {
        "id": job_id, "model_type": model_type.value,
        "metrics": metrics, "X_uri": X_uri, "y_uri": y_uri,
        "created_at": datetime.now().isoformat(),
    }
    job = TimeSeriesTrainingJob(
        id=job_id, model_type=model_type, status="completed",
        config=config, metrics=metrics, val_y_true=yv.astype(float).tolist(),
        val_y_pred=y_pred.astype(float).tolist(), val_y_score=y_score.tolist(),
    )
    return job, payload, record


def save_and_register(
    payload: dict[str, Any], record: dict[str, Any],
    root: Path, model_subdir: str = "model.pt",
) -> str:
    """Persist the payload and wire model_path into both ``record`` and the job."""
    model_dir = root / record["id"]
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = str(model_dir / model_subdir)
    torch.save(payload, model_path)
    record["model_path"] = model_path
    return model_path


def load_and_predict(
    model_path: str, build_model_fn: Callable[..., nn.Module],
    X_uri: str, input_size_key: str = "input_size",
    window_size_key: str = "window_size", num_classes_key: str = "num_classes",
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load a saved checkpoint and run inference. Returns ``(payload, checkpoint)``.

    The caller writes ``payload`` (y_pred, y_score) to disk.
    """
    payload = torch.load(model_path, weights_only=True)
    model = build_model_fn(
        input_size=payload[input_size_key], window_size=payload[window_size_key],
        num_classes=payload[num_classes_key],
    )
    model.load_state_dict(payload["state_dict"], strict=False)
    model.eval()
    X = to_windows(load_array(X_uri), payload[window_size_key]).astype(np.float32)
    X = apply_scaler(X, payload["scaler_mean"], payload["scaler_scale"])
    with torch.no_grad():
        probs = torch.softmax(model(torch.from_numpy(X)), dim=1).numpy()
    y_pred, y_score = probs.argmax(axis=1), (probs[:, 1] if probs.shape[1] > 1 else probs[:, 0])
    return {"y_pred": y_pred, "y_score": y_score}, payload
