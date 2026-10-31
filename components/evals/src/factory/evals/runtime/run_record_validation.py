"""Semantic validation for canonical evaluation-run records."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any


def validate_evaluation_run(payload: dict[str, Any]) -> str | None:
    """Return a clear inconsistency reason, or ``None`` when valid."""
    total = payload["total_cases"]
    passed = payload["passed_cases"]
    failed = payload["failed_cases"]
    if not all(_count(value) for value in (total, passed, failed)):
        return "total_cases, passed_cases, and failed_cases must be non-negative integers"
    if passed + failed != total:
        return "passed_cases + failed_cases must equal total_cases"

    rows = payload["case_results"]
    scores = payload["case_scores"]
    if len(rows) != total or len(scores) != total:
        return "case_results and case_scores lengths must equal total_cases"
    if not all(isinstance(row, dict) for row in rows):
        return "case_results must contain objects"
    if any(not isinstance(row.get("passed"), bool) for row in rows):
        return "every case_result must contain a boolean passed value"
    if any(not _score(row.get("score")) for row in rows):
        return "every case_result must contain a finite score in [0, 1]"
    if any(not _score(score) for score in scores):
        return "case_scores must contain finite values in [0, 1]"
    if any(not _equal(float(row["score"]), float(score))
           for row, score in zip(rows, scores, strict=True)):
        return "case_scores must match case_results scores positionally"

    row_passed = sum(row["passed"] for row in rows)
    if row_passed != passed:
        return "passed_cases must equal passing case_results"
    expected_rate = passed / total if total else 0.0
    expected_average = sum(float(score) for score in scores) / total if total else 0.0
    expected_verdict, policy_error = _expected_verdict(payload, total, expected_rate, expected_average)
    if policy_error:
        return policy_error
    if payload["verdict"] != expected_verdict:
        return f"verdict must be {expected_verdict} for these case results"
    if not _equal(payload["pass_rate"], expected_rate):
        return "pass_rate must equal passed_cases / total_cases"
    if not _equal(payload["avg_score"], expected_average):
        return "avg_score must equal the mean of case_scores"
    return _validate_summary(payload.get("summary", {}), total, passed, failed,
                             expected_rate, expected_average)




def _expected_verdict(
    payload: dict[str, Any], total: int, rate: float, average: float,
) -> tuple[str, str | None]:
    policy_fields = ("policy_ref", "reviewer_tool_scope", "rubric_digest")
    if payload.get("source") != "review-gate":
        if any(field in payload for field in policy_fields):
            return "FAIL", "policy fields require source=review-gate"
        return ("PASS" if total > 0 and payload["passed_cases"] == total else "FAIL"), None
    ref = payload.get("policy_ref")
    if not isinstance(ref, dict):
        return "FAIL", "review-gate requires policy_ref"
    try:
        from .review_policy import get_review_policy
        policy = get_review_policy(str(ref.get("policy_id", "")))
    except ValueError:
        return "FAIL", "review-gate policy is unknown"
    manifest = ref.get("manifest_digest")
    if not isinstance(manifest, str) or not re.fullmatch(r"[0-9a-f]{64}", manifest):
        return "FAIL", "review-gate manifest digest is invalid"
    scope = list(policy.allowed_tool_scope)
    expected_rubric = hashlib.sha256(policy.rubric.encode()).hexdigest()
    expected_ref = {
        "schema_version": policy.schema_version, "policy_id": policy.policy_id,
        "manifest_digest": manifest, "min_pass_rate": policy.min_pass_rate,
        "min_avg_score": policy.min_avg_score,
    }
    if ref != expected_ref or payload.get("reviewer_tool_scope") != scope:
        return "FAIL", "review-gate policy reference or scope is inconsistent"
    if payload.get("rubric_digest") != expected_rubric:
        return "FAIL", "review-gate rubric digest is inconsistent"
    passed = total > 0 and rate >= policy.min_pass_rate and average >= policy.min_avg_score
    return ("PASS" if passed else "FAIL"), None
def _validate_summary(
    summary: dict[str, Any], total: int, passed: int, failed: int,
    rate: float, average: float,
) -> str | None:
    if not isinstance(summary, dict):
        return "summary must be an object"
    expected = {
        "total_cases": total, "passed": passed, "passed_cases": passed,
        "failed": failed, "failed_cases": failed,
        "pass_rate": rate, "avg_score": average, "overall_score": average,
    }
    for key, value in expected.items():
        if key in summary and not _equal(summary[key], value):
            return f"summary.{key} is inconsistent with the run"
    return None


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _score(value: Any) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
    )


def _equal(left: Any, right: Any) -> bool:
    try:
        return math.isclose(float(left), float(right), abs_tol=0.0005)
    except (TypeError, ValueError):
        return left == right
