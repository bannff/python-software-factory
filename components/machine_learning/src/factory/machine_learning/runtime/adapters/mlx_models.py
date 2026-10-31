"""MLX classifier modules for time-series prediction.

Mirrors :mod:`torch_models` for Apple's MLX framework so the same LSTM
and TCN architectures can be trained with GPU/Neural Engine acceleration
on M-series Silicon. The module surface (``LSTMClassifier`` /
``TCNClassifier``) is intentionally identical to the torch variants so
:mod:`mlx_timeseries` can swap implementations behind the
:class:`TimeSeriesTrainingPort` protocol.

MLX specifics that shaped this module:

* ``mlx.nn.LSTM`` is single-layer only (no ``num_layers``) and
  sequence-major — input shape is ``(seq_len, batch, features)`` rather
  than PyTorch's ``batch_first=True`` ``(batch, seq_len, features)``.
  We transpose in ``forward`` so callers can keep using the
  conventional ``(batch, seq, features)`` layout. The :class:`LSTMClassifier`
  exposes a ``num_layers`` constructor argument for API parity with
  the torch adapter, but it is documented as a no-op (single layer
  only); the parameter is accepted so existing call sites work
  without modification.
* ``mlx.nn.Conv1d`` is also sequence-major — its weight is
  ``(out, kernel, in)`` and the input is ``(batch, length, channels)``
  (NLC), unlike PyTorch's NCHW. No transpose needed at the model
  boundary, but the tensor layout differs from the torch TCN.
* Dropout has no ``self.training`` flag — MLX modules don't switch
  mode automatically. We expose a ``training: bool`` argument on
  ``__call__`` so the training loop can drive it.
"""

from __future__ import annotations

from .mlx_platform import require_mlx_platform

require_mlx_platform()

import mlx.core as mx  # noqa: E402
import mlx.nn as nn  # noqa: E402


class LSTMClassifier(nn.Module):
    """Single-layer LSTM followed by a linear classification head.

    The final hidden state of the LSTM is fed to a fully connected
    layer to produce per-class logits. The interface accepts the
    conventional ``(batch, seq_len, features)`` shape and transposes
    internally because ``mlx.nn.LSTM`` only consumes ``(seq, batch, feat)``.

    Note:
        ``num_layers`` is accepted for API parity with the torch
        adapter but is ignored: Apple's MLX ships only a single-layer
        LSTM cell, and manually stacking two cells gave a 2-3x
        parameter blow-up with degraded convergence in our
        parity tests. The single-layer variant is the supported
        configuration for the MLX backend.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 1,
        num_classes: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        # Single-layer LSTM only (MLX constraint). ``num_layers`` is
        # silently pinned to 1 — see the class docstring.
        del num_layers
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size)
        # Output-side dropout applied to the last hidden state during
        # training; matches the spirit of the torch adapter's
        # inter-layer dropout. Skipped at inference.
        self.dropout = nn.Dropout(p=dropout) if dropout > 0 else None
        self.fc = nn.Linear(hidden_size, num_classes)

    def __call__(self, x: mx.array, training: bool = False) -> mx.array:
        # x: (batch, seq_len, features) -> (seq_len, batch, features) for MLX LSTM.
        x = mx.transpose(x, (1, 0, 2))
        out, _ = self.lstm(x)
        # out: (seq_len, batch, hidden) -> (batch, hidden) (last time step).
        last = out[-1]
        if self.dropout is not None and training:
            last = self.dropout(last)
        return self.fc(last)


class TCNClassifier(nn.Module):
    """Temporal Convolutional Network with a linear classification head.

    A stack of ``Conv1d -> ReLU -> Dropout`` blocks expands the channel
    dimension while preserving the sequence length via
    ``padding=(kernel_size - 1) // 2`` (same-length padding). The final
    channel's last time step is mapped to class logits.

    MLX's ``Conv1d`` consumes ``(batch, length, channels)`` (NLC), so
    callers can pass a 3D batch without reordering; the final linear
    head indexes the last position in the length dimension.
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
        self.dropout_p = dropout

        # Same-length padding keeps the temporal dimension invariant
        # through every block so blocks can be stacked freely.
        padding = (kernel_size - 1) // 2
        layers: list[nn.Module] = []
        in_channels = input_size
        for out_channels in num_channels:
            layers.append(nn.Conv1d(
                in_channels=in_channels, out_channels=out_channels,
                kernel_size=kernel_size, padding=padding,
            ))
            layers.append(nn.ReLU())
            in_channels = out_channels
        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], num_classes)

    def __call__(self, x: mx.array, training: bool = False) -> mx.array:
        # x: (batch, seq_len, features) — MLX Conv1d wants (batch, length, channels).
        out = self.network(x)
        if training and self.dropout_p > 0:
            # Inline dropout to avoid a sequential-layer flag.
            keep = 1.0 - self.dropout_p
            mask = mx.random.bernoulli(p=keep, shape=out.shape)
            out = out * mask / keep
        # Take the last time step of the deepest feature map.
        return self.fc(out[:, -1, :])
