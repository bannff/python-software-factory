"""Fail-closed evidence and leakage checks for edge routing examples."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from pydantic import ValidationError

from .contracts import DatasetQualityResults
from .edge_routing_contracts import EdgeRoutingExample
from .quality_edge_routing_evidence import verify_routing_evidence
from .validation import validate_edge_routing_records

_REQUIRED_SPLITS = frozenset({"train", "validation", "test"})


def _result(failures: list[str], success: str = "passed") -> str:
    return f"failed: {', '.join(sorted(failures))}" if failures else success


def _split_leaks(records: list[Any], name: str) -> list[str]:
    membership: dict[str, set[str]] = {}
    for record in records:
        value = record
        for part in name.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        if value is not None:
            membership.setdefault(str(value), set()).add(record.split)
    return sorted(value for value, splits in membership.items() if len(splits) > 1)


def _route_consistent(record: Any) -> bool:
    candidates = record.features.candidates
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    eligible = record.features.eligible_candidate_ids
    if len(candidate_ids) != len(set(candidate_ids)) or len(eligible) != len(set(eligible)):
        return False
    if not set(eligible).issubset(candidate_ids):
        return False
    selected = record.executed_route
    return selected is None or selected.candidate_id in eligible


def _time_ordered(record: Any) -> bool:
    decision = record.features.decision_at
    if record.features.source_event_at > decision:
        return False
    if any(candidate.observed_at > decision
           for candidate in record.features.candidates):
        return False
    if any(candidate.expires_at <= decision
           for candidate in record.features.candidates
           if candidate.candidate_id in record.features.eligible_candidate_ids):
        return False
    route = record.executed_route
    if route is None:
        return True
    if route.selected_at < decision:
        return False
    outcome = record.outcome
    if outcome is None:
        return True
    if outcome.observed_at < route.selected_at:
        return False
    review = outcome.review
    return review is None or review.reviewed_at >= outcome.observed_at


def _reviewed_live_label(record: Any) -> bool:
    route, outcome = record.executed_route, record.outcome
    return (
        route is not None
        and outcome is not None
        and outcome.provenance_kind == "ditto_sdk_live"
        and outcome.review is not None
        and outcome.review.verdict == "accepted"
    )


def evaluate_edge_routing_quality(records: list[Any]) -> DatasetQualityResults:
    """Validate every row before a routing dataset can be published."""
    raw_ids: list[str] = []
    by_id: dict[str, set[str]] = {}
    for raw in records:
        try:
            record = EdgeRoutingExample.model_validate(raw)
        except ValidationError:
            continue  # The schema check reports the invalid row.
        raw_ids.append(record.record_id)
        canonical = json.dumps(
            record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode()
        by_id.setdefault(record.record_id, set()).add(hashlib.sha256(canonical).hexdigest())
    try:
        validated = list(validate_edge_routing_records(records))
    except ValueError as error:
        validated = []
        schema = f"failed: {error}"
    else:
        schema = "passed"

    duplicate_ids = sorted(key for key, count in Counter(raw_ids).items() if count > 1)
    collisions = sorted(key for key, digests in by_id.items() if len(digests) > 1)

    present = {record.split for record in validated}
    missing = sorted(_REQUIRED_SPLITS - present)
    evidence = [(record, verify_routing_evidence(record)) for record in validated]
    isolation_fields = {
        "episode_split_isolation": "features.group_id",
        "session_split_isolation": "features.session_id",
        "task_split_isolation": "features.task_id",
        "source_event_split_isolation": "features.source_event_id",
        "source_digest_split_isolation": "features.source_event_ref.sha256",
        "candidate_snapshot_split_isolation": "features.candidate_snapshot_ref.sha256",
        "execution_digest_split_isolation": "executed_route.execution_ref.sha256",
        "outcome_digest_split_isolation": "outcome.outcome_ref.sha256",
        "adjudication_digest_split_isolation": "outcome.review.adjudication_ref.sha256",
    }
    checks = {
        "record_count": f"passed: {len(records)}" if records else "failed: 0 records",
        "schema": schema,
        "record_ids": _result(duplicate_ids),
        "record_id_content_collisions": _result(collisions),
        "required_splits": _result(missing),
        "evidence_integrity": _result([
            record.record_id for record, (integrity, _) in evidence if not integrity
        ], "passed: all referenced bytes match SHA-256 through no-follow reads"),
        "evidence_semantics": _result([
            record.record_id for record, (_, semantics) in evidence if not semantics
        ], "passed: typed evidence agrees with every routing record field and link"),
        "candidate_route_consistency": _result([
            record.record_id for record in validated if not _route_consistent(record)
        ]),
        "time_order": _result([
            record.record_id for record in validated if not _time_ordered(record)
        ]),
        "reviewed_label_structure": _result([
            record.record_id for record in validated if not _reviewed_live_label(record)
        ], "passed: every row claims an accepted reviewed live-SDK outcome"),
        # The sealed collector attests a fixed visual-observation run, not
        # a routing decision. A routing collector must bind the host-verified
        # run index/manifest and SDK pin to this record's execution, outcome,
        # and adjudication digests before this gate can become passable.
        "trusted_run_provenance": (
            "failed: routing-specific sealed SDK collector attestation unavailable"
        ),
    }
    for check_name, field in isolation_fields.items():
        checks[check_name] = _result(_split_leaks(validated, field))
    if not validated:
        checks["reviewed_label_structure"] = "failed: no reviewed live-SDK outcomes"
    return DatasetQualityResults(checks=checks)
