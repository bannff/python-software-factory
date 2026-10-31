"""Canonical immutable document helpers for durable Evals records."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .run_artifacts import json_safe_copy

SCHEMA_VERSION = 2
EVAL_RESULTS_COLLECTION = "eval_results"
EVALUATION_RUN_RECORD_KIND = "evaluation_run"
EVALUATION_SCORE_PROJECTION_RECORD_KIND = "evaluation_score_projection"
_RECORD_STATES = {
    EVALUATION_RUN_RECORD_KIND: "completed",
    EVALUATION_SCORE_PROJECTION_RECORD_KIND: "scored",
}
_UNAUTHENTICATED_FIELDS = frozenset({"content_hash"})


def utc_timestamp() -> str:
    """Return one UTC RFC3339 timestamp for a completed record."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def expected_terminal_state(record_kind: str) -> str | None:
    """Return the terminal state for a supported immutable record kind."""
    return _RECORD_STATES.get(record_kind)


def semantic_content_hash(record: dict[str, Any]) -> str:
    """Hash the canonical persisted record, excluding only its self-hash."""
    semantic = {
        key: value for key, value in json_safe_copy(record).items()
        if key not in _UNAUTHENTICATED_FIELDS
    }
    encoded = json.dumps(semantic, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"


def document_id(run_id: str, record_kind: str) -> str:
    """Return the isolated durable document ID for a record kind."""
    prefix = (
        "eval" if record_kind == EVALUATION_RUN_RECORD_KIND else "eval-score"
    )
    return f"{prefix}-v{SCHEMA_VERSION}-{run_id}"


def record_pointer(doc_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable reference used by downstream projections."""
    return {
        "collection": EVAL_RESULTS_COLLECTION,
        "doc_id": doc_id,
        "record_kind": record["record_kind"],
        "schema_version": record["schema_version"],
        "revision": f"v{record['schema_version']}",
        "content_hash": record["content_hash"],
    }


def projection_key(pointer: dict[str, Any]) -> str:
    """Return the stable projection identity for an immutable record."""
    return f"eval-record:{pointer['content_hash']}"


def build_record(
    *, run_id: str, record_kind: str, terminal_state: str,
    payload: dict[str, Any], timestamp: str = "",
) -> tuple[str, dict[str, Any]]:
    """Build one JSON-safe, content-addressed terminal evaluation record."""
    if not run_id:
        raise ValueError("run_id is required")
    expected_state = _RECORD_STATES.get(record_kind)
    if expected_state != terminal_state:
        raise ValueError(f"invalid record kind/state: {record_kind}/{terminal_state}")
    safe_payload = json_safe_copy(payload)
    safe_payload.pop("timestamp", None)
    safe_payload.pop("content_hash", None)
    semantic = {
        **safe_payload,
        "schema_version": SCHEMA_VERSION,
        "record_kind": record_kind,
        "terminal_state": terminal_state,
        "run_id": run_id,
    }
    record = {**semantic, "timestamp": timestamp or utc_timestamp()}
    record["content_hash"] = semantic_content_hash(record)
    return document_id(run_id, record_kind), record


def build_run_request(
    report: Any, run_id: str, agent: dict[str, Any], source: str,
    duration_ms: float, artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a retryable ``evals_record_run`` request from an Evals report."""
    cases = report.case_results
    report_summary = report.summary
    total = int(report_summary.get("total_evaluation_rows", len(cases)) or 0)
    summary = dict(report_summary)
    if "total_evaluation_rows" in report_summary:
        summary["input_case_count"] = report_summary.get("total_cases", 0)
        summary["total_cases"] = total
    passed = sum(bool(case.get("passed")) for case in cases)
    scores = [float(case.get("score", 0.0) or 0.0) for case in cases]
    request = {
        "run_id": run_id,
        "experiment_name": report.experiment_name,
        "verdict": "PASS" if total and passed == total else "FAIL",
        "pass_rate": float(summary.get("pass_rate", passed / total if total else 0.0) or 0.0),
        "avg_score": float(summary.get("overall_score", sum(scores) / len(scores) if scores else 0.0) or 0.0),
        "total_cases": total,
        "passed": passed,
        "failed_cases": total - passed,
        "case_results": cases,
        "case_scores": scores,
        "evaluators_used": report.evaluator_names,
        "agent": agent,
        "source": source,
        "duration_ms": duration_ms,
        "timestamp": utc_timestamp(),
        "summary": summary,
    }
    if artifacts is not None:
        request["artifacts"] = artifacts
    return request
