"""PatchTST classifier — thin wrapper around ``transformers.PatchTSTForClassification``.

Wraps the real HuggingFace PatchTST implementation (Nie et al., ICLR
2023) instead of a hand-rolled patch-embedding + TransformerEncoder
stack (bd:python-factory-q1jsr .2, SDK-First tenet). Field names were
verified against the installed ``transformers`` package
(``transformers>=4.46.0``, tested against 5.5.4):

* ``num_input_channels`` <- ``n_channels``
* ``context_length`` <- ``seq_len``
* ``patch_length`` / ``patch_stride`` <- ``patch_len`` (non-overlapping,
  matches the prior model's ``stride == patch_len`` invariant)
* ``num_targets`` <- ``num_classes``
* ``d_model``, ``num_attention_heads`` <- ``n_heads``,
  ``num_hidden_layers`` <- ``n_layers``

``PatchTSTForClassification.forward(past_values=...)`` returns a
``PatchTSTForClassificationOutput`` with ``.prediction_logits`` shaped
``(batch, num_targets)`` — confirmed does NOT require
``context_length`` to be divisible by ``patch_length`` (HF pads
internally), unlike the previous hand-rolled model. We keep the
constructor signature identical so ``patchtst_timeseries.py::_build_patchtst``
does not need to change its call shape.
"""

from __future__ import annotations

import torch
from torch import nn

__all__ = ["PatchTSTClassifier"]


class PatchTSTClassifier(nn.Module):
    """PatchTST binary/multi-class classifier for windowed multivariate time-series.

    Args:
        n_channels: Number of input features.
        seq_len: Length of the input window (matches ``window_size``).
        patch_len: Patch length; stride is fixed equal to ``patch_len``
            (non-overlapping patches), matching the prior design.
        d_model: Transformer hidden dimension.
        n_heads: Number of attention heads.
        n_layers: Number of transformer encoder layers.
        num_classes: Output dimension (2 for binary failure detection).
        dropout: Dropout applied to attention, position encoding, and head.
    """

    def __init__(
        self,
        n_channels: int,
        seq_len: int,
        patch_len: int = 5,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 3,
        num_classes: int = 2,
        dropout: float = 0.1,
    ) -> None:
        try:
            from transformers import PatchTSTConfig, PatchTSTForClassification
        except ImportError as exc:
            raise ImportError(
                "PatchTST requires optional ML extras: uv sync --group ml"
            ) from exc
        super().__init__()
        config = PatchTSTConfig(
            num_input_channels=n_channels,
            context_length=seq_len,
            patch_length=patch_len,
            patch_stride=patch_len,
            num_hidden_layers=n_layers,
            d_model=d_model,
            num_attention_heads=n_heads,
            num_targets=num_classes,
            attention_dropout=dropout,
            positional_dropout=dropout,
            head_dropout=dropout,
            ff_dropout=dropout,
            scaling=None,  # windows are already standardized upstream
        )
        self.model = PatchTSTForClassification(config)
        self.n_channels = n_channels
        self.seq_len = seq_len

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, channels) — PatchTSTForClassification's
        # ``past_values`` expects exactly this layout, so no transpose
        # is needed (unlike the hand-rolled model, which wanted
        # channels-first for its Conv1d patch embedder).
        return self.model(past_values=x).prediction_logits
