"""Edge-routing public contract facade and dataset readiness assessment."""
from __future__ import annotations

from typing import Iterable, Literal

from .edge_routing_core import (
    _RoutingValue, _stable_id, _utc_time, _immutable_sequence, RoutingContentRef,
    RoutingCandidateSnapshot, RoutingDecisionFeatures,
)
from .edge_routing_outcomes import (
    EdgeRoutingExample, ExecutedRoute, RoutingOutcomeEvidence, RoutingReview,
)
from pydantic import Field, model_validator


class RoutingDatasetReadiness(_RoutingValue):
    """A bounded training-readiness signal, before artifact integrity gates."""

    status: Literal["ready", "no_labels", "quality_blocked"]
    training_allowed: bool
    reason: str = Field(min_length=1, max_length=200)
    reviewed_label_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _coherent(self) -> RoutingDatasetReadiness:
        if self.training_allowed != (self.status == "ready"):
            raise ValueError("Readiness status and training_allowed disagree")
        return self

def is_reviewed_observed_outcome(record: EdgeRoutingExample) -> bool:
    """Only executed, accepted-review live SDK outcomes carry routing labels."""
    outcome = record.outcome
    return bool(
        record.executed_route is not None
        and outcome is not None
        and outcome.provenance_kind == "ditto_sdk_live"
        and outcome.review is not None
        and outcome.review.verdict == "accepted"
    )

def routing_dataset_readiness(
    records: Iterable[EdgeRoutingExample | dict],
) -> RoutingDatasetReadiness:
    """Require reviewed labels, full quality, and trusted run provenance."""
    from .validation import validate_edge_routing_records
    from .quality_edge_routing import evaluate_edge_routing_quality

    counts = {"train": 0, "validation": 0, "test": 0}
    counted_ids: set[str] = set()
    validated = list(validate_edge_routing_records(records))
    for record in validated:
        if record.record_id not in counted_ids and is_reviewed_observed_outcome(record):
            counts[record.split] += 1
            counted_ids.add(record.record_id)
    total = sum(counts.values())
    missing = [split for split, count in counts.items() if count == 0]
    if missing:
        return RoutingDatasetReadiness(
            status="no_labels", training_allowed=False,
            reason=f"No reviewed live SDK outcome labels in {', '.join(missing)} split(s)",
            reviewed_label_count=total,
        )
    quality = evaluate_edge_routing_quality(validated)
    trusted = quality.checks.get("trusted_run_provenance", "failed: not evaluated")
    if not quality.passed or not (trusted == "passed" or trusted.startswith("passed:")):
        failed = {
            name for name, result in quality.checks.items()
            if result.startswith("failed:")
        }
        if not trusted.startswith("passed"):
            failed.add("trusted_run_provenance")
        priority = (
            "trusted_run_provenance", "evidence_integrity", "session_split_isolation",
        )
        ordered = [name for name in priority if name in failed]
        ordered.extend(sorted(failed - set(ordered)))
        return RoutingDatasetReadiness(
            status="quality_blocked", training_allowed=False,
            reason=f"Quality gates failed: {', '.join(ordered[:3])} ({len(failed)} checks)",
            reviewed_label_count=total,
        )
    return RoutingDatasetReadiness(
        status="ready", training_allowed=True,
        reason="Reviewed live SDK labels and trusted evidence passed quality gates",
        reviewed_label_count=total,
    )
