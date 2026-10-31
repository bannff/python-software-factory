"""PyTorch training utilities for the time-series adapter.

Holds the model factory and the early-stopping training loop used by
``torch_timeseries.py``. Kept separate so the adapter file stays under
the 200-LOC ceiling and so the loop can be unit-tested independently.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from ..ports import TimeSeriesModelType
from .torch_models import LSTMClassifier, TCNClassifier

__all__ = ["build_model", "train_loop"]


def build_model(
    model_type: TimeSeriesModelType, input_size: int, num_classes: int,
) -> nn.Module:
    """Construct an LSTM or TCN classifier for the given input shape."""
    if model_type == TimeSeriesModelType.lstm:
        return LSTMClassifier(input_size=input_size, num_classes=num_classes)
    if model_type == TimeSeriesModelType.tcn:
        return TCNClassifier(input_size=input_size, num_classes=num_classes)
    raise NotImplementedError(f"Model type '{model_type.value}' is not supported.")


def train_loop(
    model: nn.Module, loader: DataLoader,
    X_val: torch.Tensor, y_val: torch.Tensor,
    criterion: nn.Module, optimizer: optim.Optimizer,
    epochs: int, patience: int,
) -> dict[str, torch.Tensor]:
    """Train with early stopping; return the best-observed state dict."""
    best_val, best_state, no_improve = float("inf"), None, 0
    for _ in range(epochs):
        model.train()
        for xb, yb in loader:
            optimizer.zero_grad()
            criterion(model(xb), yb).backward()
            # Gradient clipping keeps LSTM/TCN training stable: a single
            # mini-batch with a large-norm input can otherwise send the
            # hidden state to NaN and the rest of the epoch is wasted.
            # max_norm=1.0 is the conventional value for sequence models
            # (see Merity et al. 2017 "Regularizing and Optimizing LSTM
            # Language Models") and is cheap.
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
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
