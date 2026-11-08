"""Game reward handler — a finished game becomes learning signal (#384).

Subscribes to ``game.finished`` and routes the learner's signed reward through
the learning seam's ``game-outcome`` source → ``reward.computed`` → the
existing memory / blockchain fan-out. The learner is player ``1`` (the agent
under training; the opponent's reward is its mirror in a zero-sum game).
Idempotent: the run id is ``game-{game_id}`` and the key is source-scoped, so a
replayed ``game.finished`` publishes at most one reward.
"""
from __future__ import annotations

import logging
from typing import Any

from .learning_result import normalize_learning_result
from .models import Event
from .rewards_handler import _emit_reward_event

logger = logging.getLogger(__name__)
_LEARNER = "1"

__all__ = ["handle_game_reward"]


def handle_game_reward(event: Event, invoker: Any) -> dict[str, Any]:
    """Score the learner's side of a finished game; skip when there is no reward."""
    payload = event.payload
    game_id = str(payload.get("game_id") or "")
    rewards = payload.get("reward")
    value = rewards.get(_LEARNER) if isinstance(rewards, dict) else None
    if not game_id or value is None:
        return {"skipped": True, "reason": "no game_id/learner reward"}
    run_id = f"game-{game_id}"
    game_type = str(payload.get("game_type") or "")
    try:
        result = normalize_learning_result(invoker(
            "learning_compute_reward", run_id=run_id, domain_class=game_type,
            workflow_type="game", game_reward=value,
        ))
    except Exception as exc:
        logger.warning("game reward: compute failed (%s)", type(exc).__name__)
        return {"skipped": True, "error": "reward_computation_failed"}
    if result is None:
        return {"skipped": True, "error": "reward_computation_failed"}
    if not result.get("source_id"):
        return {"skipped": True, "reason": "no reward signal"}
    payload["run_id"], payload["domain_class"] = run_id, game_type
    reward = _emit_reward_event(invoker, event, result, key_suffix="game")
    return {"game_id": game_id, "run_id": run_id, "reward": reward}
