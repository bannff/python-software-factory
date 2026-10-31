"""Learning runtime — iterate reward sources, emit a neutral result.

Reward production is PURE registry iteration: the engine asks every
registered source for a signal and each source decides whether it applies.
ZERO domain-equality branches, zero domain literals, zero cross-brick
imports — the discipline that keeps the reward layer agnostic
(bd python-factory-pfvo9, meta-architect verdict 978a674d).

The default registry seeds four independent built-in sources:
``gt-findings``, ``llm-judge``, ``user-feedback``, and ``telemetry``. Packs
may register more sources without changing this engine.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .adapters.gt_findings import GtFindingsRewardSource
from .adapters.llm_judge import LlmJudgeRewardSource
from .adapters.telemetry import TelemetryRewardSource
from .adapters.user_feedback import UserFeedbackRewardSource
from .models import RewardSignal
from .registry import RewardSourceRegistry, get_registry

logger = logging.getLogger(__name__)


class LearningRuntime:
    """Aggregates reward signals from all registered sources."""

    def __init__(self, registry: RewardSourceRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    @property
    def registry(self) -> RewardSourceRegistry:
        """The reward-source registry backing this runtime."""
        return self._registry

    def compute(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Collect signals from every source; return a neutral result.

        The result carries the winning (highest-scalar) signal as the
        ``primary`` for the events emitter, the full ``signals`` list for
        observability, and the primary's raw source evidence for migration
        back-compat. Evidence is non-authoritative; canonical reward fields
        come from the validated signal.
        """
        signals = self._collect(run_ctx, invoker)
        primary = _select_primary(signals)
        return {
            "signals": [s.as_dict() for s in signals],
            "source_id": primary.source_id if primary else "",
            "verdict": primary.verdict if primary else "no_reward",
            "scalar": primary.scalar if primary else 0.0,
            "reward_value": primary.reward_value if primary else 0.0,
            "wallet_id": primary.wallet_id if primary else "wallet-kiro-agent",
            "provenance": primary.provenance if primary else {},
            # Migration-window back-compat for the events emitter.
            "raw": primary.raw if primary else {},
            "scoring": (primary.raw.get("scoring", {}) if primary else {}),
        }

    def _collect(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> list[RewardSignal]:
        out: list[RewardSignal] = []
        for src in self._registry.sources():
            sid = getattr(src, "source_id", "unknown")
            try:
                sig = src.signal_or_none(run_ctx, invoker)
            except Exception as exc:  # never propagate a source failure
                logger.warning(
                    "reward source failed source=%s error_type=%s",
                    sid, type(exc).__name__,
                )
                sig = None
            if sig is not None:
                out.append(sig)
        return out


def _select_primary(signals: list[RewardSignal]) -> RewardSignal | None:
    """Pick the highest-scalar signal (deterministic; first wins on tie)."""
    if not signals:
        return None
    return max(signals, key=lambda s: s.scalar)


_runtime: LearningRuntime | None = None


def get_runtime() -> LearningRuntime:
    """Return the process-wide runtime with the four built-in sources seeded."""
    global _runtime
    if _runtime is None:
        registry = get_registry()
        registry.register_builtin(GtFindingsRewardSource())
        registry.register_builtin(LlmJudgeRewardSource())
        registry.register_builtin(UserFeedbackRewardSource())
        registry.register_builtin(TelemetryRewardSource())
        _runtime = LearningRuntime(registry)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (test hygiene)."""
    global _runtime
    _runtime = None


__all__ = ["LearningRuntime", "get_runtime", "reset_runtime"]
