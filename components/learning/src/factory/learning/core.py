"""Core constants for the learning brick.

The reward layer is domain-agnostic: a reward signal is a neutral
``{scalar, verdict, provenance}`` triple produced by a polymorphic
``RewardSourcePort``. The closed neutral verdict set mirrors the existing
``reward.computed`` contract (events brick) — the learning brick layers
these names ABOVE any per-source detail and never invents domain-specific
verdicts (bd python-factory-pfvo9).
"""

from __future__ import annotations

# Neutral verdicts on the reward.computed wire (events learning_contracts).
REWARDED = "rewarded"
NO_REWARD = "no_reward"
# Negative signal (down-vote, tool failure): valuable learning, but NEVER
# mints tokens — reward_value floors at 0 while the signed scalar is kept.
PENALIZED = "penalized"

REWARD_VERDICTS: frozenset[str] = frozenset({REWARDED, NO_REWARD, PENALIZED})

# Default reward-token shaping: tokens = max(0, scalar) * SCALE. Keeps the
# pre-seam f1*100 behavior byte-identical (gt-findings scalar == F1 >= 0).
TOKEN_SCALE: float = 100.0

DEFAULT_WALLET: str = "wallet-kiro-agent"

__all__ = [
    "REWARDED",
    "NO_REWARD",
    "PENALIZED",
    "REWARD_VERDICTS",
    "TOKEN_SCALE",
    "DEFAULT_WALLET",
]
