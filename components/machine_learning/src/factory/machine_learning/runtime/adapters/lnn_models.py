"""Liquid Neural Network (LNN) classifier — wraps ``ncps.torch.LTC``.

Uses the real Liquid Time-Constant (LTC) cell implementation from the
``ncps`` package (Hasani et al., "Liquid Time-constant Networks",
AAAI 2021) instead of a hand-rolled Euler-discretised cell. ``ncps``
is the reference PyTorch/TensorFlow implementation released by the
paper's authors (bd:python-factory-q1jsr .3, SDK-First tenet).

``ncps.torch.LTC(input_size, units, return_sequences=True,
batch_first=True)`` returns ``(output_sequence, final_hidden_state)``
when called — verified against the installed package
(``ncps==1.0.1``): output shape ``(batch, seq_len, units)``, hidden
shape ``(batch, units)``.

LoRA is intentionally out of scope here: LTC cells have no
``q_proj``/``v_proj``-style attention modules for PEFT to target, and
the LNN adapter was never in scope for LoRA (bd .5 only covers the
generic PEFT backend + Chronos).
"""

from __future__ import annotations

import torch
from ncps.torch import LTC
from torch import nn

__all__ = ["LNNClassifier"]


class LNNClassifier(nn.Module):
    """Stacked ``ncps`` LTC cells with a linear classification head.

    Mirrors the previous hand-rolled model's public surface: same
    constructor signature, same ``forward`` input/output contract
    ``(batch, seq_len, input_size) -> (batch, num_classes)``. We
    average the last ``pool_last`` hidden states (temporal pooling)
    rather than taking just the final step, matching the prior
    design's rationale — LTC dynamics are continuous-time and the most
    informative activation is often slightly before the final step.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 32,
        n_layers: int = 1,
        num_classes: int = 2,
        pool_last: int = 4,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {n_layers}")
        self.layers = nn.ModuleList()
        self.layer_norms = nn.ModuleList()
        in_dim = input_size
        for _ in range(n_layers):
            self.layers.append(
                LTC(in_dim, hidden_size, return_sequences=True, batch_first=True),
            )
            # LayerNorm keeps the per-layer hidden distribution
            # well-conditioned for the next layer's input projection.
            self.layer_norms.append(nn.LayerNorm(hidden_size))
            in_dim = hidden_size
        self.pool_last = pool_last
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor, timespans: torch.Tensor) -> torch.Tensor:
        """Run native LTC layers with mandatory pre-normalized elapsed time."""
        if (
            not isinstance(timespans, torch.Tensor)
            or x.ndim != 3 or timespans.ndim != 2
            or tuple(timespans.shape) != tuple(x.shape[:2])
            or not torch.is_floating_point(timespans)
            or not torch.isfinite(timespans).all()
            or not torch.all(timespans > 0)
        ):
            raise ValueError(
                "LNN timespans must be finite positive floating data matching X",
            )
        for layer, norm in zip(self.layers, self.layer_norms):
            layer_ts = timespans.unsqueeze(-1).expand(-1, -1, layer.state_size)
            seq, _hidden = layer(x, timespans=layer_ts)
            x = norm(seq)
        # Average the last ``pool_last`` timesteps for a stable summary.
        pooled = x[:, -self.pool_last:, :].mean(dim=1)
        return self.fc(self.dropout(pooled))
