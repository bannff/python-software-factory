"""PyTorch classifier modules for time-series prediction.

This module defines two neural network architectures used by the
``torch_timeseries`` adapter:

* :class:`LSTMClassifier` - a recurrent model suitable for short to
  medium-length sequences where temporal dependencies are captured by
  hidden state propagation.
* :class:`TCNClassifier` - a temporal convolutional network that uses
  stacked 1D causal-style convolutions with same-length padding to
  extract multi-scale features.

Both models share the same interface contract:
    * Constructor takes ``input_size`` (feature dimension) and
      ``num_classes`` (output dimension).
    * ``forward(x)`` accepts a tensor of shape ``(batch, seq_len,
      input_size)`` and returns logits of shape ``(batch, num_classes)``.

Persistence, training loops, and optimizer logic are intentionally
out of scope; this module is consumed by ``torch_timeseries.py``.
"""

from __future__ import annotations

import torch
from torch import nn


class LSTMClassifier(nn.Module):
    """Stacked LSTM followed by a linear classification head.

    The final hidden state of the top LSTM layer is fed to a fully
    connected layer to produce per-class logits. Dropout is applied
    between LSTM layers when ``num_layers > 1`` to mitigate
    overfitting on small datasets.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        # Inter-layer dropout is only meaningful when stacking >1 layer.
        lstm_dropout = dropout if num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout,
        )
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size) -> lstm out: (batch, seq_len, hidden_size)
        out, _ = self.lstm(x)
        # Use only the last time step for classification.
        return self.fc(out[:, -1, :])


class TCNClassifier(nn.Module):
    """Temporal Convolutional Network with a linear classification head.

    A stack of ``Conv1d -> ReLU -> Dropout`` blocks expands the channel
    dimension while preserving the sequence length via
    ``padding=(kernel_size - 1) // 2`` (same-length padding). The
    final channel's last time step is mapped to class logits.
    """

    def __init__(
        self,
        input_size: int,
        num_channels: list[int] | None = None,
        kernel_size: int = 3,
        num_classes: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if num_channels is None:
            num_channels = [32, 32, 64]

        layers: list[nn.Module] = []
        in_channels = input_size
        # Same-length padding keeps the temporal dimension invariant
        # through every block so blocks can be stacked freely.
        padding = (kernel_size - 1) // 2
        for out_channels in num_channels:
            layers.append(
                nn.Conv1d(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    padding=padding,
                )
            )
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            in_channels = out_channels
        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size) -> (batch, features, seq_len) for Conv1d.
        x = x.permute(0, 2, 1)
        out = self.network(x)
        # Pool by taking the final time step of the deepest feature map.
        return self.fc(out[:, :, -1])
