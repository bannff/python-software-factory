"""User-feedback reward source (built-in) — explicit human signal.

A thumbs up/down is an EXPLICIT reward, not an evaluation: the verdict IS
the signal, so this source reads it straight from the run context and maps
it to a signed scalar (up → +1.0 reward, down → -1.0 penalty). It ignores
the invoker (no LLM/tool call) and abstains when no feedback verdict is
present, so it never fires on ordinary runs (bd python-factory-pfvo9).

Down-votes are first-class learning signal: the signed scalar is preserved
(``PENALIZED`` verdict, zero tokens) so the loop learns from what NOT to do.
Wiring the FE thumbs → ``chat.feedback`` event → this source is slice 2.
"""

from __future__ import annotations

from typing import Any, Callable

from ..models import RewardSignal

# Explicit verdict → signed scalar. Up rewards, down penalizes (never mints).
_VERDICT_SCALAR: dict[str, float] = {"up": 1.0, "down": -1.0}


class UserFeedbackRewardSource:
    """Maps an explicit thumbs verdict to a signed RewardSignal."""

    source_id = "user-feedback"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Return a signal for an explicit thumbs verdict; abstain otherwise."""
        verdict = str(run_ctx.get("feedback_verdict") or "").strip().lower()
        scalar = _VERDICT_SCALAR.get(verdict)
        if scalar is None:
            return None  # no explicit feedback on this run → abstain
        return RewardSignal.from_scalar(
            self.source_id,
            scalar,
            provenance={
                "feedback_verdict": verdict,
                "thread_id": run_ctx.get("thread_id", ""),
                "message_id": run_ctx.get("message_id", ""),
            },
            raw={"scoring": {"f1": max(0.0, scalar)}, "feedback_verdict": verdict},
        )


__all__ = ["UserFeedbackRewardSource"]
