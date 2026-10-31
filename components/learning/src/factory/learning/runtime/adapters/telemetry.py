"""Telemetry reward source (built-in) — failures become learning signal.

Process health is an orthogonal axis to task quality: a run can produce
good findings yet thrash on tool errors. This source turns the
``tool_error_rate`` that's ALREADY computed every workflow iteration into a
signed NEGATIVE scalar so failures shape behavior (recalled as a cautionary
learning), not just dashboards (bd python-factory-hv5rv).

Cheap-to-abstain (meta-architect 86f91240): a clean run (error_rate absent
or ``<= floor``) returns ``None`` — otherwise every workflow would mint a
zero-scalar reward (noise). It reads the rate straight from ``run_ctx``
(the ``metrics.record`` payload) and never queries the events bus.
Isolation is structural: telemetry rides ``metrics.record`` (one hop after
``graph.completed``), so it never shares a ``compute()`` call with the
gt-findings task reward — no ``_select_primary`` change needed.
"""

from __future__ import annotations

from typing import Any, Callable

from ..models import RewardSignal

# Below this error rate a run is "clean" — abstain (no penalty, no noise).
_ERROR_FLOOR = 0.0


class TelemetryRewardSource:
    """Maps a run's tool_error_rate to a signed negative RewardSignal."""

    source_id = "telemetry"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Penalize proportional to tool_error_rate; abstain on a clean run."""
        raw_rate = run_ctx.get("tool_error_rate")
        if raw_rate is None:
            return None
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            return None
        if rate <= _ERROR_FLOOR:
            return None  # clean run → no penalty, no reward spam
        scalar = -min(rate, 1.0)  # signed negative; reward_value floors at 0
        return RewardSignal.from_scalar(
            self.source_id,
            scalar,
            provenance={"tool_error_rate": round(rate, 3)},
            raw={"scoring": {"f1": 0.0}, "tool_error_rate": round(rate, 3)},
        )


__all__ = ["TelemetryRewardSource"]
