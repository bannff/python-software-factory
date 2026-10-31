"""Conditional TimeGAN neural-network modules.

Two small torch modules that mirror the un-conditional
:class:`timegan_models.Generator` /
:class:`timegan_models.Discriminator` but accept a one-hot
failure-mode vector alongside the latent noise / signal:

* :class:`ConditionalGenerator` — LSTM(latent_dim + n_modes → hidden_dim) →
  Linear(hidden_dim → n_features). The one-hot mode is broadcast over
  every time step and concatenated with the latent noise along the
  feature axis; this is the standard cGAN conditioning pattern.
* :class:`ConditionalDiscriminator` — LSTM(n_features + n_modes → hidden_dim)
  → Linear → Sigmoid → 1. The same one-hot broadcast is concatenated
  with the window before the LSTM, so the discriminator can use the
  mode label as a side-channel to detect mode-real mismatches.

Both modules store ``n_modes`` so the training/sampling adapter can
broadcast the one-hot without re-passing the dimension. Keeping these
classes out of ``timegan_conditional.py`` keeps that adapter file
under the 200-LOC factory ceiling.
"""

from __future__ import annotations

import torch
from torch import nn


class ConditionalGenerator(nn.Module):
    """LSTM generator conditioned on a one-hot failure-mode vector.

    Input:
        ``z`` (B, T, latent_dim) — random latent noise.
        ``mode_onehot`` (B, n_modes) — one-hot failure-mode label.

    Output:
        ``(B, T, n_features)`` — synthetic window.
    """

    def __init__(self, latent_dim: int, n_modes: int, hidden_dim: int,
                 n_layers: int, n_features: int) -> None:
        super().__init__()
        self.latent_dim = int(latent_dim)
        self.n_modes = int(n_modes)
        dropout = 0.1 if n_layers > 1 else 0.0
        # Input dim = latent noise + per-step mode one-hot.
        self.lstm = nn.LSTM(
            self.latent_dim + self.n_modes, hidden_dim, n_layers,
            batch_first=True, dropout=dropout,
        )
        self.fc = nn.Linear(hidden_dim, n_features)

    def forward(self, z: torch.Tensor, mode_onehot: torch.Tensor) -> torch.Tensor:
        """Generate a synthetic window conditioned on ``mode_onehot``."""
        B, T, _ = z.shape
        # Broadcast the (B, n_modes) condition to every time step.
        c = mode_onehot.unsqueeze(1).expand(B, T, self.n_modes)
        zc = torch.cat([z, c], dim=-1)
        out, _ = self.lstm(zc)
        return self.fc(out)


class ConditionalDiscriminator(nn.Module):
    """LSTM discriminator conditioned on a one-hot failure-mode vector.

    Input:
        ``x`` (B, T, n_features) — real or generated window.
        ``mode_onehot`` (B, n_modes) — one-hot failure-mode label.

    Output:
        ``(B, 1)`` — P(window is real | mode).
    """

    def __init__(self, n_features: int, n_modes: int, hidden_dim: int,
                 n_layers: int) -> None:
        super().__init__()
        self.n_modes = int(n_modes)
        dropout = 0.1 if n_layers > 1 else 0.0
        # Input dim = signal features + per-step mode one-hot.
        self.lstm = nn.LSTM(
            n_features + self.n_modes, hidden_dim, n_layers,
            batch_first=True, dropout=dropout,
        )
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor, mode_onehot: torch.Tensor) -> torch.Tensor:
        """Score a window as real, conditioned on ``mode_onehot``."""
        B, T, _ = x.shape
        c = mode_onehot.unsqueeze(1).expand(B, T, self.n_modes)
        xc = torch.cat([x, c], dim=-1)
        out, _ = self.lstm(xc)
        return torch.sigmoid(self.fc(out[:, -1, :]))
