"""Regression gate — pure business logic.

Compares current metric values against a stored baseline and emits
BLOCK / WARN / PASS signals.  No MCP, no graph, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

GateSignal = Literal["BLOCK", "WARN", "PASS"]


@dataclass(frozen=True)
class BaselineComparison:
    """Per-metric comparison result."""

    metric_id: str
    current_value: float
    baseline_value: float
    delta: float
    delta_pct: float
    signal: GateSignal
    threshold_block: float
    threshold_warn: float


@dataclass(frozen=True)
class RegressionResult:
    """Aggregate regression gate result."""

    overall_signal: GateSignal
    comparisons: tuple[BaselineComparison, ...]
    baseline_tag: str
    compared_at: str  # ISO 8601


def _signal_for_delta(delta_pct: float, block: float, warn: float) -> GateSignal:
    """Return the gate signal for a given absolute delta percentage."""
    abs_pct = abs(delta_pct)
    if abs_pct >= block:
        return "BLOCK"
    if abs_pct >= warn:
        return "WARN"
    return "PASS"


_SIGNAL_RANK: dict[GateSignal, int] = {"PASS": 0, "WARN": 1, "BLOCK": 2}


def _worst(a: GateSignal, b: GateSignal) -> GateSignal:
    return a if _SIGNAL_RANK[a] >= _SIGNAL_RANK[b] else b


def compare_to_baseline(
    current: dict[str, float],
    baseline: dict[str, float],
    baseline_tag: str = "unknown",
    threshold_block: float = 0.05,
    threshold_warn: float = 0.02,
) -> RegressionResult:
    """Compare *current* values against *baseline* values.

    Returns a :class:`RegressionResult` with per-metric comparisons and
    an ``overall_signal`` equal to the worst individual signal.
    """
    comparisons: list[BaselineComparison] = []
    overall: GateSignal = "PASS"

    all_keys = sorted(set(current) | set(baseline))
    for key in all_keys:
        cur = current.get(key, 0.0)
        base = baseline.get(key, 0.0)
        delta = cur - base
        delta_pct = (delta / abs(base)) if base != 0 else (0.0 if delta == 0 else 1.0)
        sig = _signal_for_delta(delta_pct, threshold_block, threshold_warn)
        overall = _worst(overall, sig)
        comparisons.append(BaselineComparison(
            metric_id=key,
            current_value=cur,
            baseline_value=base,
            delta=round(delta, 8),
            delta_pct=round(delta_pct, 8),
            signal=sig,
            threshold_block=threshold_block,
            threshold_warn=threshold_warn,
        ))

    return RegressionResult(
        overall_signal=overall,
        comparisons=tuple(comparisons),
        baseline_tag=baseline_tag,
        compared_at=datetime.now(timezone.utc).isoformat(),
    )
