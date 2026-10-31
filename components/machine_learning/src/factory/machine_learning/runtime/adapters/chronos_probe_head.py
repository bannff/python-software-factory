"""Lightweight classification head trained on top of frozen/LoRA Chronos-2 embeddings.

Chronos-2 (``amazon/chronos-2``) is a 120M-parameter pretrained
time-series foundation model; we don't retrain its backbone from
scratch (that's the whole point of using a foundation model). Instead
we extract encoder embeddings for each window and train a small
linear/MLP probe on top — the "embedding-probe" design decided by the
meta-architect verdict for bd:python-factory-q1jsr .5.
"""

from __future__ import annotations

import torch
from torch import nn

__all__ = ["ChronosProbeHead"]


class ChronosProbeHead(nn.Module):
    """A 2-layer MLP classification head over pooled Chronos-2 embeddings."""

    def __init__(
        self, embedding_dim: int, num_classes: int = 2,
        hidden_dim: int | None = None, dropout: float = 0.1,
    ) -> None:
        super().__init__()
        hidden_dim = hidden_dim or max(embedding_dim // 4, num_classes * 4)
        self.net = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        return self.net(embeddings)
