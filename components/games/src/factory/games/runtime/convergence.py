"""Convergence detection for iterative game loops.

Three algorithms run simultaneously with 2-of-3 voting:
1. Patience — stop after K iterations with no improvement
2. Plateau — stop when score delta drops below epsilon
3. Regression — stop immediately if score drops below best

When 2+ algorithms agree on STOP, the loop terminates.
GameState is Pydantic-serializable = forkable for future
LATS/MCTS tree search extension.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceConfig:
    """Configuration for convergence detection."""

    patience: int = 3
    epsilon: float = 0.01
    max_iterations: int = 20
    min_iterations: int = 2


@dataclass
class ConvergenceState:
    """Tracks convergence across iterations."""

    scores: list[float] = field(default_factory=list)
    best_score: float = 0.0
    best_iteration: int = 0
    no_improve_count: int = 0
    config: ConvergenceConfig = field(default_factory=ConvergenceConfig)

    def record(self, score: float) -> None:
        """Record a new score from an iteration."""
        self.scores.append(score)
        if score > self.best_score:
            self.best_score = score
            self.best_iteration = len(self.scores) - 1
            self.no_improve_count = 0
        else:
            self.no_improve_count += 1

    def should_stop(self) -> tuple[bool, dict[str, Any]]:
        """Check if the loop should stop using 2-of-3 voting.

        Returns:
            (should_stop, details) where details includes
            per-algorithm votes and reasoning.
        """
        n = len(self.scores)
        cfg = self.config

        if n >= cfg.max_iterations:
            return True, {"reason": "max_iterations", "iteration": n}

        if n < cfg.min_iterations:
            return False, {"reason": "below min_iterations", "iteration": n}

        votes: dict[str, bool] = {}
        reasons: dict[str, str] = {}

        # 1. Patience — no improvement for K iterations
        patience_stop = self.no_improve_count >= cfg.patience
        votes["patience"] = patience_stop
        reasons["patience"] = (
            f"no improvement for {self.no_improve_count}/{cfg.patience}"
            if patience_stop
            else f"improving ({self.no_improve_count}/{cfg.patience})"
        )

        # 2. Plateau — delta below epsilon
        if n >= 2:
            delta = abs(self.scores[-1] - self.scores[-2])
            plateau_stop = delta < cfg.epsilon
            votes["plateau"] = plateau_stop
            reasons["plateau"] = (
                f"delta {delta:.4f} < epsilon {cfg.epsilon}"
                if plateau_stop
                else f"delta {delta:.4f} >= epsilon {cfg.epsilon}"
            )
        else:
            votes["plateau"] = False
            reasons["plateau"] = "not enough data"

        # 3. Regression — score dropped below best
        if n >= 2:
            regression_stop = self.scores[-1] < self.best_score * 0.95
            votes["regression"] = regression_stop
            reasons["regression"] = (
                f"score {self.scores[-1]:.4f} < 95% of best {self.best_score:.4f}"
                if regression_stop
                else f"score {self.scores[-1]:.4f} within 5% of best"
            )
        else:
            votes["regression"] = False
            reasons["regression"] = "not enough data"

        # 2-of-3 voting
        stop_votes = sum(1 for v in votes.values() if v)
        should_stop = stop_votes >= 2

        return should_stop, {
            "iteration": n,
            "score": self.scores[-1] if self.scores else 0,
            "best_score": self.best_score,
            "best_iteration": self.best_iteration,
            "votes": votes,
            "reasons": reasons,
            "stop_votes": stop_votes,
            "decision": "STOP" if should_stop else "CONTINUE",
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize convergence state."""
        return {
            "scores": self.scores,
            "best_score": self.best_score,
            "best_iteration": self.best_iteration,
            "no_improve_count": self.no_improve_count,
            "iteration_count": len(self.scores),
        }
