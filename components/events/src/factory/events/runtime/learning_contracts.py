"""Schema contracts for canonical learning-loop events."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class LearningEventPayload(BaseModel):
    """Shared payload contract for learning-loop events.

    ``workflow_id`` is the canonical identifier; ``graph_id`` is a deprecated
    alias retained for backward compatibility with pre-Workflow producers.
    The ``_normalize_workflow_id`` pre-validator backfills whichever key is
    missing and rejects mismatched values during the deprecation window.

    Removal of ``graph_id`` is intentionally deferred at least two quarters
    (tracked as a P4 follow-up) so all consumers — including external
    skills, prompts, and recipes — have time to cut over without coordinated
    big-bang releases. Until then, producers SHOULD dual-emit and new
    consumers SHOULD read ``workflow_id``.
    """

    run_id: str = Field(..., min_length=1)
    workflow_run_id: str = Field(..., min_length=1)
    workflow_id: str = Field(
        default="",
        validation_alias=AliasChoices("workflow_id", "graph_id"),
    )
    graph_id: str = Field(default="")
    session_id: str = Field(default="")
    tenant_id: str = Field(default="")
    principal_id: str = Field(default="")
    profile_id: str = Field(default="default")
    profile_version: str = Field(default="v1")
    target_app: str = Field(default="")
    workflow_type: str = Field(default="auto")
    vuln_class: str = Field(default="")
    domain_class: str = Field(
        default="",
        validation_alias=AliasChoices("domain_class", "vuln_class"),
    )
    status: str = Field(default="unknown")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_workflow_id(cls, data: Any) -> Any:
        """Backfill graph_id<->workflow_id alias and reject mismatches."""
        if not isinstance(data, dict):
            return data
        gid = data.get("graph_id")
        wid = data.get("workflow_id")
        if gid and wid and gid != wid:
            raise ValueError(
                "graph_id and workflow_id must match during deprecation window"
            )
        if gid and not wid:
            data = {**data, "workflow_id": gid}
        elif wid and not gid:
            data = {**data, "graph_id": wid}
        return data


class RewardComputedPayload(LearningEventPayload):
    """Payload for reward.computed."""

    score: float = 0
    scalar: float = 0
    precision: float = 0
    recall: float = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    reward_value: float = 0
    reward_unit: str = "tokens"
    wallet_id: str = "wallet-kiro-agent"
    verdict: str = "no_reward"
    duration_ms: int = 0
    idempotency_key: str = Field(..., min_length=1)
    reward_identity: str = ""
    # bd:python-factory-pfvo9 — additive reward-source provenance. Default
    # empty keeps existing producers/consumers byte-identical; the learning
    # brick stamps which source produced the signal + its detail.
    source_id: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)


class WalletRewardedPayload(LearningEventPayload):
    """Payload for wallet.rewarded."""

    reward_value: float = 0
    reward_unit: str = "tokens"
    transaction_id: str | None = None
    wallet_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)


class MemoryLearningStoredPayload(LearningEventPayload):
    """Payload for memory.learning_stored."""

    memory_id: str | None = None
    summary_type: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)


class LearningAppliedPayload(LearningEventPayload):
    """Fires when an agent retrieves RL learnings from memory at invocation start.

    Producer: memory brick runtime.retrieve hook when any returned memory's
    metadata.tags include `*-learnings` (the workflow_rl signature). Closure-
    observability primitive — bd python-factory-o7t8.
    """

    agent_id: str = ""
    retrieved_count: int = 0
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    query: str = ""             # producer truncates at 256 chars
    idempotency_key: str = Field(..., min_length=1)


class ConvergenceCheckedPayload(LearningEventPayload):
    """Payload for convergence.checked."""

    metric_id: str = Field(..., min_length=1)
    converged: bool
    baseline_window: str = Field(..., min_length=1)
    comparison_window: str = Field(..., min_length=1)
    metrics_recorded: int = 0
    # Regression-gate signal merged in from MetricsRuntime.detect_drift when
    # a named baseline exists for this metric. Surfaced so policy routers
    # consuming convergence.checked can act on regressions without an extra
    # round trip.
    regression_signal: str | None = None
    baseline_tag: str | None = None


# Module-level verdict constants for workflow.improvement (bd python-factory-kq6u).
# Plain strings (NOT Literal) per meta-architect Q1 verdict — Literal forces
# consumers to import the type and violates Views-as-Data. Imported by the
# improvement handler, its tests, and any future dashboard panel so the set
# stays single-sourced.
VERDICT_IMPROVED = "improved"
VERDICT_REGRESSED = "regressed"
VERDICT_STABLE = "stable"
VERDICT_BASELINE_SET = "baseline_set"


class WorkflowImprovementPayload(LearningEventPayload):
    """Payload for workflow.improvement.

    Fires after reward.computed; compares the current run's F1 to an N-run
    rolling baseline of the same (workflow_type, target_app, vuln_class) tuple
    pulled from the storage ``eval_results`` collection. Closure-observability
    primitive — answers "is this same workflow trending up against its own
    baseline?" Subscriber priority 7 on reward.computed (after convergence at
    6, before memory at 8 / wallet at 10).
    """

    current_score: float = 0.0
    baseline_score: float = 0.0
    delta: float = 0.0
    verdict: str = VERDICT_BASELINE_SET  # one of VERDICT_*
    baseline_window_n: int = 10
    baseline_run_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(..., min_length=1)


LEARNING_EVENT_MODELS: dict[str, type[BaseModel]] = {
    "reward.computed": RewardComputedPayload,
    "wallet.rewarded": WalletRewardedPayload,
    "memory.learning_stored": MemoryLearningStoredPayload,
    "convergence.checked": ConvergenceCheckedPayload,
    "learning.applied": LearningAppliedPayload,
    "workflow.improvement": WorkflowImprovementPayload,
}


def learning_event_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON schemas for all canonical learning events."""
    return {
        event_type: model.model_json_schema()
        for event_type, model in LEARNING_EVENT_MODELS.items()
    }


def validate_learning_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a canonical learning payload."""
    model = LEARNING_EVENT_MODELS.get(event_type)
    if model is None:
        raise ValueError(f"Unsupported learning event type: {event_type}")
    return model.model_validate(payload).model_dump()