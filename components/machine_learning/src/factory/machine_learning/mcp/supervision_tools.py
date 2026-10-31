"""Thin MCP registration for the S2 first-party supervision verbs.

Epics can pause, stop-at-checkpoint, adjust, or resume a training attempt
without touching in-flight processes: every verb records durable
first-party state (supervision intent / new attempt claim). See
``runtime/supervision_intents.py`` and ``runtime/supervision_claims.py``.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, ok, operational

from ..runtime.supervision_claims import (
    create_training_supervision, TrainingSupervision,
)
from ..runtime.supervision_intents import SupervisionError
from .supervision_contracts import (
    AdjustedClaimOutput, AdjustHyperparamInput, PauseTrainingInput,
    ResumeTrainingInput, StopAtCheckpointInput, SupervisionActionOutput,
)


def _dispatch(handler: Any, request: dict[str, Any]) -> ToolResult[Any]:
    """Run one supervision verb, mapping typed errors to fail envelopes.

    Runtime conflicts (the adjust verb's already-bound attempt key) are
    terminal-negative data, not a success payload: map them to a typed fail
    envelope the way the S1 CAN lifecycle tools map a non-completed terminal,
    so the caller sees the conflict reason instead of a generic
    ``tool_execution_failed`` from output-model validation.
    """
    try:
        result = handler(**request)
    except SupervisionError as exc:
        return fail(str(exc))
    if result.get("status") == "conflict":
        return fail(str(result.get("error", "supervision command conflicts")))
    return ok(result)


def register(
    mcp: Any, get_runtime: Callable[[], Any],
    service_factory: Callable[[], TrainingSupervision] | None = None,
) -> None:
    """Register four supervision verbs on the machine_learning MCP surface."""
    factory = service_factory or (lambda: create_training_supervision())

    @mcp.tool(name="ml_pause_training")
    @operational(
        input_model=PauseTrainingInput, output_model=SupervisionActionOutput,
    )
    def pause_training(attempt_id: str, reason: str = "") -> ToolResult[SupervisionActionOutput]:
        """Accept a pause command for a live training attempt."""
        return _dispatch(factory().pause, {"attempt_id": attempt_id, "reason": reason})

    @mcp.tool(name="ml_stop_at_checkpoint")
    @operational(
        input_model=StopAtCheckpointInput, output_model=SupervisionActionOutput,
    )
    def stop_at_checkpoint(
    attempt_id: str, checkpoint_name: str = "",
) -> ToolResult[SupervisionActionOutput]:
        """Stop a training attempt at its next checkpoint."""
        return _dispatch(factory().stop, {"attempt_id": attempt_id, "checkpoint_name": checkpoint_name})

    @mcp.tool(name="ml_adjust_hyperparam")
    @operational(
        input_model=AdjustHyperparamInput, output_model=AdjustedClaimOutput,
    )
    def adjust_hyperparam(
    attempt_id: str, hyperparams: dict[str, Any],
) -> ToolResult[AdjustedClaimOutput]:
        """Issue a NEW attempt claim with the adjusted hyperparams."""
        return _dispatch(factory().adjust, {"attempt_id": attempt_id, "hyperparams": hyperparams})

    @mcp.tool(name="ml_resume_training")
    @operational(
        input_model=ResumeTrainingInput, output_model=SupervisionActionOutput,
    )
    def resume_training(attempt_id: str, reason: str = "") -> ToolResult[SupervisionActionOutput]:
        """Accept a resume command for a paused training attempt."""
        return _dispatch(factory().resume, {"attempt_id": attempt_id, "reason": reason})


__all__ = ["register"]
