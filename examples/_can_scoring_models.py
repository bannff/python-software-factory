"""Torch model wrappers + training loops for the CAN evaluator scoring run.

Keeps model definitions (LSTM, TCN) and their train/predict helpers
co-located so the main scoring script stays under 200 LOC.
"""

from __future__ import annotations

import time
from typing import Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

DEFAULT_EPOCHS = 20
DEFAULT_BATCH = 64


class LSTMClassifier(nn.Module):
    """Compact LSTM head — last hidden state → class logit."""

    def __init__(self, input_size: int, hidden_size: int = 128) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # h is the final-layer final-step hidden state, shape (1, batch, hidden)
        _, (h, _) = self.lstm(x)
        return self.fc(h.squeeze(0))


class TCNClassifier(nn.Module):
    """Compact 1D CNN — same-length padding → class logit."""

    def __init__(self, input_size: int, channels: int = 64) -> None:
        super().__init__()
        self.conv = nn.Conv1d(input_size, channels, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.fc = nn.Linear(channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq, feat) → Conv1d expects (batch, feat, seq)
        h = self.relu(self.conv(x.transpose(1, 2)))
        return self.fc(h[:, :, -1])


def train_torch_model(
    model: nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH,
) -> Tuple[nn.Module, float]:
    """Train a torch classifier on 3D windowed data; return model + train time."""
    loader = DataLoader(
        TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train)),
        batch_size=batch_size, shuffle=True, drop_last=False,
    )
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    start = time.perf_counter()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad()
            logits = model(xb).squeeze(-1)
            loss = loss_fn(logits, yb.float())
            loss.backward()
            opt.step()
    return model, time.perf_counter() - start


def predict_torch(model: nn.Module, X_test: np.ndarray) -> np.ndarray:
    """Score held-out windows with a trained torch model → sigmoid scores."""
    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(torch.from_numpy(X_test)).squeeze(-1))
    return scores.numpy()
