"""Typed, content-addressed evidence checks for routing examples.

This verifies referential and semantic consistency, not live SDK authenticity.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .atomic_io import read_bytes_no_follow
from .edge_routing_contracts import EdgeRoutingExample, RoutingCandidateSnapshot
from .local_inputs import path_from_uri_no_follow

_MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["1.0"]
    record_id: str


class _SourceEvent(_Evidence):
    kind: Literal["source_event"]
    source_event_id: str
    group_id: str
    session_id: str
    task_id: str
    source_event_at: datetime


class _CandidateSet(_Evidence):
    kind: Literal["candidate_snapshot"]
    decision_at: datetime
    candidates: tuple[RoutingCandidateSnapshot, ...]
    eligible_candidate_ids: tuple[str, ...]


class _Execution(_Evidence):
    kind: Literal["route_execution"]
    source_event_id: str
    candidate_id: str
    selected_at: datetime
    selection_propensity: float


class _Outcome(_Evidence):
    kind: Literal["route_outcome"]
    run_id: str
    sdk_version: str
    candidate_id: str
    observed_at: datetime
    succeeded: bool
    execution_sha256: str


class _Adjudication(_Evidence):
    kind: Literal["route_adjudication"]
    reviewer_ref: str
    verdict: Literal["accepted", "rejected"]
    reviewed_at: datetime
    outcome_sha256: str


def _refs(record: Any) -> list[Any]:
    refs = [record.features.source_event_ref, record.features.candidate_snapshot_ref]
    if record.executed_route is not None:
        refs.append(record.executed_route.execution_ref)
    if record.outcome is not None:
        refs.append(record.outcome.outcome_ref)
        if record.outcome.review is not None:
            refs.append(record.outcome.review.adjudication_ref)
    return refs


def _load_refs(record: Any) -> list[bytes] | None:
    payloads: list[bytes] = []
    for ref in _refs(record):
        try:
            payload = read_bytes_no_follow(
                path_from_uri_no_follow(ref.uri), max_bytes=_MAX_EVIDENCE_BYTES,
            )
            parsed = json.loads(
                payload, object_pairs_hook=_unique_json_keys,
                parse_constant=lambda value: _invalid_constant(value),
            )
        except (OSError, UnicodeError, ValueError):
            return None
        if hashlib.sha256(payload).hexdigest() != ref.sha256 or not isinstance(parsed, dict):
            return None
        payloads.append(payload)
    return payloads


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def _unique_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence JSON key")
        result[key] = value
    return result


def _evidence_semantics(record: Any, payloads: list[bytes]) -> bool:
    features, route, outcome = record.features, record.executed_route, record.outcome
    expected: list[_Evidence] = [
        _SourceEvent(
            schema_version="1.0", record_id=record.record_id, kind="source_event",
            source_event_id=features.source_event_id, group_id=features.group_id,
            session_id=features.session_id, task_id=features.task_id,
            source_event_at=features.source_event_at,
        ),
        _CandidateSet(
            schema_version="1.0", record_id=record.record_id, kind="candidate_snapshot",
            decision_at=features.decision_at, candidates=features.candidates,
            eligible_candidate_ids=features.eligible_candidate_ids,
        ),
    ]
    if route is not None:
        expected.append(_Execution(
            schema_version="1.0", record_id=record.record_id, kind="route_execution",
            source_event_id=features.source_event_id, candidate_id=route.candidate_id,
            selected_at=route.selected_at, selection_propensity=route.selection_propensity,
        ))
    if outcome is not None and route is not None:
        expected.append(_Outcome(
            schema_version="1.0", record_id=record.record_id, kind="route_outcome",
            run_id=outcome.run_id, sdk_version=outcome.sdk_version,
            candidate_id=route.candidate_id, observed_at=outcome.observed_at,
            succeeded=outcome.succeeded, execution_sha256=route.execution_ref.sha256,
        ))
        if outcome.review is not None:
            expected.append(_Adjudication(
                schema_version="1.0", record_id=record.record_id,
                kind="route_adjudication", reviewer_ref=outcome.review.reviewer_ref,
                verdict=outcome.review.verdict, reviewed_at=outcome.review.reviewed_at,
                outcome_sha256=outcome.outcome_ref.sha256,
            ))
    if len(expected) != len(payloads):
        return False
    try:
        return all(
            type(value).model_validate_json(payload) == value
            for value, payload in zip(expected, payloads, strict=True)
        )
    except ValidationError:
        return False


def verify_routing_evidence(record: EdgeRoutingExample) -> tuple[bool, bool]:
    """Return (byte integrity, typed semantic consistency) for all record refs."""
    payloads = _load_refs(record)
    if payloads is None:
        return False, False
    return True, _evidence_semantics(record, payloads)
