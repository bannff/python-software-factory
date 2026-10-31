"""TimeGAN neural-network modules.

Two small torch modules are shared between the training adapter and
the sample path:

* :class:`Generator` — LSTM(latent_dim → hidden_dim) → Linear(hidden_dim → n_features).
  Maps latent noise ``(B, T, latent_dim)`` to a synthetic window
  ``(B, T, n_features)`` matching the training-data shape.
* :class:`Discriminator` — LSTM(n_features → hidden_dim) → Sigmoid → 1.
  Reads the final hidden state of a window and outputs a probability
  that the window is real.

Both modules follow the same constructor contract: ``(input_dim,
hidden_dim, n_layers, output_dim)`` for the Generator and
``(input_dim, hidden_dim, n_layers)`` for the Discriminator (output
dim is fixed at 1).
"""

from __future__ import annotations

import torch
from torch import nn


class Generator(nn.Module):
    """LSTM generator: latent noise (B, T, latent_dim) -> (B, T, n_features)."""

    def __init__(self, latent_dim: int, hidden_dim: int, n_layers: int, n_features: int) -> None:
        super().__init__()
        dropout = 0.1 if n_layers > 1 else 0.0
        self.lstm = nn.LSTM(latent_dim, hidden_dim, n_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_dim, n_features)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(z)
        return self.fc(out)


class Discriminator(nn.Module):
    """LSTM discriminator: window (B, T, n_features) -> real prob (B, 1)."""

    def __init__(self, n_features: int, hidden_dim: int, n_layers: int) -> None:
        super().__init__()
        dropout = 0.1 if n_layers > 1 else 0.0
        self.lstm = nn.LSTM(n_features, hidden_dim, n_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return torch.sigmoid(self.fc(out[:, -1, :]))
