"""Game-outcome reward source (built-in) — a finished game is learning signal.

``game.finished`` carries a zero-sum per-player reward ({"1": +1, "2": -1}).
The caller picks the learner's entry and passes it as ``game_reward``; this
source keeps the sign (a loss is a PENALIZED learning, never a mint) and
abstains when the run was not a game, so ordinary runs never fire it.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Callable

from ..models import RewardSignal


class GameOutcomeRewardSource:
    """Maps a finished game's signed reward to a RewardSignal."""

    source_id = "game-outcome"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Return a signal for a game reward in [-1, 1]; abstain otherwise."""
        raw = run_ctx.get("game_reward")
        if raw is None or isinstance(raw, bool):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if not isfinite(value):
            return None
        scalar = max(-1.0, min(1.0, value))
        return RewardSignal.from_scalar(
            self.source_id, scalar,
            provenance={"game_reward": scalar},
            raw={"scoring": {"f1": max(0.0, scalar)}, "game_reward": scalar},
        )


__all__ = ["GameOutcomeRewardSource"]
