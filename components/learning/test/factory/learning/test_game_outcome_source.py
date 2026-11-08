"""game-outcome reward source: a finished game's signed reward is learning signal (#384)."""
from __future__ import annotations

from factory.learning.runtime.adapters.game_outcome import GameOutcomeRewardSource


def test_win_is_a_positive_reward() -> None:
    sig = GameOutcomeRewardSource().signal_or_none({"game_reward": 1.0, "run_id": "game-1"}, None)
    assert sig is not None and sig.source_id == "game-outcome"
    assert sig.scalar == 1.0 and sig.verdict == "rewarded"


def test_loss_is_penalized_and_never_mints() -> None:
    sig = GameOutcomeRewardSource().signal_or_none({"game_reward": -1.0}, None)
    assert sig is not None
    assert sig.scalar == -1.0 and sig.reward_value == 0.0 and sig.verdict == "penalized"


def test_abstains_without_a_game_reward_or_on_garbage() -> None:
    src = GameOutcomeRewardSource()
    assert src.signal_or_none({}, None) is None
    assert src.signal_or_none({"game_reward": None}, None) is None
    assert src.signal_or_none({"game_reward": "x"}, None) is None
    assert src.signal_or_none({"game_reward": float("nan")}, None) is None


def test_clamps_to_unit_range() -> None:
    sig = GameOutcomeRewardSource().signal_or_none({"game_reward": 7.5}, None)
    assert sig is not None and sig.scalar == 1.0
