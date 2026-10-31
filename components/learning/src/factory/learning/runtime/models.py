"""Neutral reward-signal model for the learning brick.

``RewardSignal`` is the domain-agnostic unit every ``RewardSourcePort``
produces. It carries a normalized ``scalar`` (-1..1; negative = penalty
signal that never mints), a neutral ``verdict``, source-specific
``provenance`` (free-form detail — e.g. precision/recall for the
gt-findings source), and ``raw`` (the source's own result dict,
preserved so the events ``reward.computed`` emitter can stay byte-identical
during the migration window, bd python-factory-pfvo9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core import DEFAULT_WALLET, NO_REWARD, PENALIZED, REWARDED, TOKEN_SCALE


@dataclass
class RewardSignal:
    """A neutral, source-agnostic reward signal."""

    source_id: str
    scalar: float = 0.0
    verdict: str = NO_REWARD
    reward_value: float = 0.0
    wallet_id: str = DEFAULT_WALLET
    provenance: dict[str, Any] = field(default_factory=dict)
    # The source's own raw result dict (migration-window back-compat).
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_scalar(
        cls,
        source_id: str,
        scalar: float,
        *,
        wallet_id: str = DEFAULT_WALLET,
        provenance: dict[str, Any] | None = None,
        raw: dict[str, Any] | None = None,
    ) -> "RewardSignal":
        """Build a signal, shaping tokens + verdict from the scalar.

        Tokens floor at zero — ``reward_value = max(0, scalar) * TOKEN_SCALE``
        — so a negative scalar NEVER mints, while the signed scalar is kept
        for learning/distillation. Verdict: REWARDED when tokens > 0,
        PENALIZED when the (signed) scalar is negative, else NO_REWARD. For
        scalar >= 0 this is byte-identical to the pre-signed behavior.
        """
        s = _clamp(scalar)
        amount = round(max(0.0, s) * TOKEN_SCALE, 2)
        if amount > 0:
            verdict = REWARDED
        elif s < 0:
            verdict = PENALIZED
        else:
            verdict = NO_REWARD
        return cls(
            source_id=source_id,
            scalar=s,
            verdict=verdict,
            reward_value=amount,
            wallet_id=wallet_id,
            provenance=dict(provenance or {}),
            raw=dict(raw or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize for transport across the MCP boundary."""
        return {
            "source_id": self.source_id,
            "scalar": self.scalar,
            "verdict": self.verdict,
            "reward_value": self.reward_value,
            "wallet_id": self.wallet_id,
            "provenance": self.provenance,
        }


def _clamp(value: float) -> float:
    """Clamp a scalar into [-1, 1]; non-numeric → 0.0.

    The signed range preserves negative learning signal (down-votes, tool
    failures) distinctly from a zero/absent signal — token minting floors
    at 0 separately in ``from_scalar`` (bd:python-factory-pfvo9).
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-1.0, min(1.0, v))


__all__ = ["RewardSignal"]
