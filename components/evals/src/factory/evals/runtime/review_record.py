"""Threshold review rows into the canonical immutable run-record request."""
from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict

from .review_policy import get_review_policy


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    policy_id: str
    verdict: str
    pass_rate: float
    avg_score: float
    request: dict[str, Any]


def decide_review(
    run_id: str, policy_id: str, manifest_digest: str,
    rows: list[dict[str, Any]], agent: dict[str, Any],
) -> ReviewDecision:
    policy = get_review_policy(policy_id)
    total = len(rows)
    passed = sum(bool(row["test_pass"]) for row in rows)
    rate = passed / total if total else 0.0
    average = sum(float(row["score"]) for row in rows) / total if total else 0.0
    verdict = (
        "PASS" if total and rate >= policy.min_pass_rate
        and average >= policy.min_avg_score else "FAIL"
    )
    case_results = [
        {
            "evaluator": row["evaluator"], "passed": row["test_pass"],
            "score": float(row["score"]), "reason": row["reason"],
        }
        for row in rows
    ]
    policy_ref = {
        "schema_version": policy.schema_version, "policy_id": policy.policy_id,
        "manifest_digest": manifest_digest,
        "min_pass_rate": policy.min_pass_rate,
        "min_avg_score": policy.min_avg_score,
    }
    summary = {
        "total_cases": total, "passed": passed, "failed": total - passed,
        "pass_rate": rate, "avg_score": average, "overall_score": average,
        "policy_id": policy.policy_id,
    }
    request = {
        "run_id": run_id, "experiment_name": policy.policy_id,
        "verdict": verdict, "pass_rate": rate, "avg_score": average,
        "total_cases": total, "passed": passed, "failed_cases": total - passed,
        "case_results": case_results,
        "case_scores": [float(row["score"]) for row in rows],
        "evaluators_used": list(policy.evaluator_names), "agent": agent,
        "source": "review-gate", "summary": summary,
        "policy_ref": policy_ref,
        "reviewer_tool_scope": list(policy.allowed_tool_scope),
        "rubric_digest": hashlib.sha256(policy.rubric.encode()).hexdigest(),
    }
    return ReviewDecision(
        policy_id=policy.policy_id, verdict=verdict,
        pass_rate=rate, avg_score=average, request=request,
    )


__all__ = ["ReviewDecision", "decide_review"]
