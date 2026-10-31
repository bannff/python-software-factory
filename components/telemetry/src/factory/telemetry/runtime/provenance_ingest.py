"""Scoped Telemetry provenance retention and replay semantics."""
from __future__ import annotations

from datetime import datetime, timezone

from .provenance_models import (
    AuthenticatedTelemetryContext, TelemetryIdempotencyRecord, TelemetryIngestBatch,
    TelemetryIngestResult, TelemetryIngestItem, TelemetryItemOutcome, TelemetryStoredRecord,
)
from .provenance_policy import PolicyDecision, RetentionPolicy
from .policy_config import compose_retention_policy
from .provenance_store import ProvenanceStore
from .provenance_support import fingerprint, telemetry_ref


def _idempotency(
    context: AuthenticatedTelemetryContext, kind: str, key: str,
    value_fingerprint: str, outcome_ref: str, persisted_at: datetime,
    decision: PolicyDecision | None = None, outcome: str = "retained",
) -> TelemetryIdempotencyRecord:
    evidence = decision.evidence if decision else {
        "policy_version": "telemetry-default-v1", "outcome": outcome,
    }
    return TelemetryIdempotencyRecord(
        tenant_id=context.tenant_id, producer_id=context.producer_id,
        key_kind=kind, key=key, fingerprint=value_fingerprint,
        outcome_ref=outcome_ref, persisted_at=persisted_at,
        policy_version=str(evidence.get("policy_version", "unknown")),
        policy_outcome=str(evidence.get("outcome", outcome)),
        policy_evidence=evidence,
    )


def _duplicate_result(batch: TelemetryIngestBatch, status: str) -> TelemetryIngestResult:
    outcomes = [TelemetryItemOutcome(
        source_id=item.source_id, status=status, retryable=False,
        reason=None if status == "duplicate" else "batch_fingerprint_conflict",
    ) for item in batch.items]
    return TelemetryIngestResult(
        batch_id=batch.batch_id, status=status, outcomes=outcomes,
        retryable_source_ids=[],
    )


def ingest(
    store: ProvenanceStore, batch: TelemetryIngestBatch,
    context: AuthenticatedTelemetryContext, policy: RetentionPolicy | None = None,
) -> TelemetryIngestResult:
    """Retain an authenticated batch with policy and atomic replay handling."""
    batch = TelemetryIngestBatch.model_validate(batch)
    policy = policy or compose_retention_policy()
    decisions = [policy.apply(context, item) for item in batch.items]
    batch_fingerprint = fingerprint({
        "batch": batch.model_dump(mode="json"), "policy": policy.version,
        "decisions": [decision.evidence for decision in decisions],
    })
    retained_at = datetime.now(timezone.utc)
    outcomes: list[TelemetryItemOutcome] = []
    source_records: list[tuple[TelemetryIdempotencyRecord, TelemetryStoredRecord | None]] = []
    seen: set[str] = set()
    unique_items: list[tuple[TelemetryIngestItem, PolicyDecision]] = []
    for item, decision in zip(batch.items, decisions, strict=True):
        if item.source_id in seen:
            outcomes.append(TelemetryItemOutcome(
                source_id=item.source_id, status="conflict", retryable=False,
                reason="duplicate_source_in_batch",
            ))
            continue
        seen.add(item.source_id)
        unique_items.append((item, decision))
        effective_item = decision.item
        item_fingerprint = fingerprint({
            "item": item.model_dump(mode="json"), "policy": decision.evidence,
        })
        reference = telemetry_ref(context, item.source_id)
        source = _idempotency(
            context, "source", item.source_id, item_fingerprint,
            reference if effective_item is not None else "sampled:" + reference,
            retained_at, decision,
        )
        stored = None if effective_item is None else TelemetryStoredRecord(
            telemetry_ref=reference, context=context, item=effective_item,
            retained_at=retained_at, policy_version=policy.version,
            policy_outcome=decision.outcome, policy_evidence=decision.evidence,
        )
        source_records.append((source, stored))

    batch_outcome = "mixed" if len({decision.outcome for decision in decisions}) > 1 else (decisions[0].outcome if decisions else "retained")
    batch_record = _idempotency(
        context, "batch", batch.batch_id, batch_fingerprint,
        f"batch:{batch.batch_id}", retained_at, outcome=batch_outcome,
    )
    committed = store.atomic_ingest(batch_record, source_records)
    if committed.existing_batch is not None:
        status = (
            "duplicate"
            if committed.existing_batch.fingerprint == batch_fingerprint
            else "conflict"
        )
        return _duplicate_result(batch, status)
    existing_sources = committed.existing_sources
    for item, decision in unique_items:
        prior = existing_sources.get(item.source_id)
        if prior is not None:
            status = "duplicate" if prior.fingerprint == fingerprint({"item": item.model_dump(mode="json"), "policy": decision.evidence}) else "conflict"
            outcomes.append(TelemetryItemOutcome(
                source_id=item.source_id, status=status, retryable=False,
                reason=None if status == "duplicate" else "source_fingerprint_conflict",
                policy_version=prior.policy_version, policy_outcome=prior.policy_outcome,
            ))
        elif decision.item is None:
            outcomes.append(TelemetryItemOutcome(
                source_id=item.source_id, status="sampled_out", retryable=False,
                reason="sampled_out", policy_version=policy.version,
                policy_outcome=decision.outcome,
            ))
        else:
            outcomes.append(TelemetryItemOutcome(
                source_id=item.source_id, status="accepted", telemetry_ref=telemetry_ref(context, item.source_id),
                retryable=False, policy_version=policy.version,
                policy_outcome=decision.outcome,
            ))
    statuses = {outcome.status for outcome in outcomes}
    if "conflict" in statuses:
        status = "conflict" if statuses == {"conflict"} else "partial_failure"
    elif statuses == {"duplicate"}:
        status = "duplicate"
    else:
        status = "accepted"
    return TelemetryIngestResult(
        batch_id=batch.batch_id, status=status, outcomes=outcomes,
        retryable_source_ids=[],
    )


__all__ = ["ingest"]
