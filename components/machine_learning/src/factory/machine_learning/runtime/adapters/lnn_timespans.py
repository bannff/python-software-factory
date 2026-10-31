"""Timespans-aware LTC training loop (bd:python-factory-q1jsr.4).

``transformer_training.train_classifier`` can't be reused as-is for
timespans-driven LTC training: it calls ``model(xb)`` with no way to
thread a second ``timespans`` tensor through the loop, and the file is
already at its 189/200-LOC ceiling with no room to add that branch.
This module owns a small, standalone train loop that calls
``model(xb, timespans=tsb)`` at every step, but still reuses every
other shared primitive (``to_windows``, ``fit_scaler_transform``,
``apply_scaler``, ``load_array``, ``temporal_split_with_shuffle_fallback``,
``compute_classification_metrics``) so there's no duplicated logic.

Alignment trick: ``temporal_split_with_shuffle_fallback`` only knows
how to shuffle/split two arrays (``X``, ``y``) in lockstep. To keep a
third array (``timespans``) aligned through the same shuffle, we
concatenate it as an extra trailing channel of ``X`` before the split
call and slice it back off immediately after -- and critically, before
the scaler ever sees it, since raw elapsed-time values are not a
feature to normalise.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ..ports import TimeSeriesModelType, TimeSeriesTrainingConfig, TimeSeriesTrainingJob
from .lnn_native import checkpoint_payload, timing_artifact
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics
from .torch_data import apply_scaler, fit_scaler_transform, load_array, to_windows


def _train_loop(
    model: nn.Module, loader: DataLoader,
    X_val: torch.Tensor, ts_val: torch.Tensor, y_val: torch.Tensor,
    optimizer: optim.Optimizer, epochs: int, patience: int, grad_clip: float,
) -> dict[str, torch.Tensor]:
    """Same early-stopping shape as ``transformer_training._train_loop``,
    but every ``model(...)`` call also passes ``timespans``.
    """
    criterion = nn.CrossEntropyLoss()
    best_val, best_state, no_improve = float("inf"), None, 0
    for _ in range(epochs):
        model.train()
        for xb, tsb, yb in loader:
            optimizer.zero_grad()
            criterion(model(xb, timespans=tsb), yb).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(X_val, timespans=ts_val), y_val).item()
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    return best_state or {k: v.detach().clone() for k, v in model.state_dict().items()}


def train_lnn_with_timespans(
    build_model_fn: Callable[[int, int, int], nn.Module],
    X_uri: str, y_uri: str, timespans_uri: str,
    config: TimeSeriesTrainingConfig, grad_clip: float = 0.5,
    job_id: str | None = None,
) -> tuple[TimeSeriesTrainingJob, dict[str, Any], dict[str, Any]]:
    """Train an LTC classifier driven by real per-step elapsed time.

    Returns ``(job, payload, record)`` -- the same 3-tuple shape as
    ``transformer_training.train_classifier`` -- so
    ``lnn_timeseries.py`` can persist the result identically via
    ``save_and_register``.
    """
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    X = to_windows(load_array(X_uri), config.window_size).astype(np.float32)
    y = load_array(y_uri).ravel().astype(np.int64)
    n_samples, window_size, n_features = X.shape
    if n_samples != len(y):
        raise ValueError(f"X has {n_samples} windows but y has {len(y)} labels")
    raw_timespans, timing_scale, timing_digest = timing_artifact(
        timespans_uri, (n_samples, window_size),
    )
    timespans = (raw_timespans / timing_scale).astype(np.float32)
    n_classes = max(int(y.max()) + 1, 2)

    # Concat timespans as a trailing channel so the split keeps X, y,
    # and timespans in lockstep; slice it back off right after.
    X_ext = np.concatenate([X, timespans[..., None]], axis=-1)
    Xt_ext, yt, Xv_ext, yv = temporal_split_with_shuffle_fallback(
        X_ext, y, config.validation_split, config.seed,
    )
    Xt, ts_t = Xt_ext[..., :n_features].copy(), Xt_ext[..., n_features].copy()
    Xv, ts_v = Xv_ext[..., :n_features].copy(), Xv_ext[..., n_features].copy()

    Xt, scaler_mean, scaler_scale = fit_scaler_transform(Xt, len(Xt))
    Xv = apply_scaler(Xv, scaler_mean, scaler_scale)

    model = build_model_fn(n_features, window_size, n_classes)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(Xt), torch.from_numpy(ts_t), torch.from_numpy(yt)),
        batch_size=config.batch_size, shuffle=True,
    )
    X_val_t = torch.from_numpy(Xv)
    ts_val_t = torch.from_numpy(ts_v)
    y_val_t = torch.from_numpy(yv)
    best_state = _train_loop(
        model, loader, X_val_t, ts_val_t, y_val_t,
        optim.Adam(model.parameters(), lr=config.learning_rate),
        config.epochs, config.early_stopping_patience, grad_clip,
    )
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        probs = torch.softmax(model(X_val_t, timespans=ts_val_t), dim=1).numpy()
    y_pred = probs.argmax(axis=1)
    y_score = probs[:, 1] if probs.shape[1] > 1 else probs[:, 0]
    metrics = compute_classification_metrics(yv, y_pred, y_score)

    job_id = job_id or str(uuid.uuid4())
    payload = checkpoint_payload(
        best_state, n_features, config.window_size, n_classes,
        scaler_mean, scaler_scale, timing_scale, (n_samples, window_size),
        timing_digest,
    )
    record = {
        "id": job_id, "model_type": TimeSeriesModelType.lnn.value,
        "metrics": metrics, "X_uri": X_uri, "y_uri": y_uri,
        "timespans_uri": timespans_uri,
        "created_at": datetime.now().isoformat(),
    }
    job = TimeSeriesTrainingJob(
        id=job_id, model_type=TimeSeriesModelType.lnn, status="completed",
        config=config, metrics=metrics, val_y_true=yv.astype(float).tolist(),
        val_y_pred=y_pred.astype(float).tolist(), val_y_score=y_score.tolist(),
    )
    return job, payload, record
