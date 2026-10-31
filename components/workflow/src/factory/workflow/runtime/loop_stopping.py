"""Pure stopping-rule evaluation for durable Workflow loops."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .loop_models import CycleDisposition, LoopRecord, LoopState


@dataclass(frozen=True, slots=True)
class StopDecision:
    state: LoopState
    reason: str


def evaluate_stop(
    loop: LoopRecord, *, now: datetime, sentinel_exists: bool,
    disposition: CycleDisposition | None = None,
) -> StopDecision | None:
    if now.tzinfo is None:
        raise ValueError("stop evaluation time must be timezone-aware")
    if sentinel_exists:
        return StopDecision(LoopState.STOPPED, "stop_file")
    if disposition is CycleDisposition.SUCCESS:
        return StopDecision(LoopState.SUCCEEDED, "goal_complete")
    if disposition is CycleDisposition.BLOCKED:
        return StopDecision(LoopState.BLOCKED, "agent_blocked")
    if disposition is CycleDisposition.FAILED:
        return StopDecision(LoopState.FAILED, "cycle_failed")
    if loop.max_cycles and loop.last_settled_cycle >= loop.max_cycles:
        return StopDecision(LoopState.EXHAUSTED, "cycle_cap")
    if loop.runtime_deadline is not None and now >= loop.runtime_deadline:
        return StopDecision(LoopState.EXHAUSTED, "runtime_budget")
    return None


__all__ = ["StopDecision", "evaluate_stop"]
