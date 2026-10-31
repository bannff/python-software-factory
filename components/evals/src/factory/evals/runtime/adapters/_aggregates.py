"""Derive aggregate fields from case_results.

Single source of truth for pass_rate / passed / failed / total_cases / avg_score.
Used at persist-time (so new runs are always correct) and at read-time (so
legacy records with missing aggregates render consistently).

Scale: pass_rate in [0.0, 1.0]; avg_score same scale as individual case .score.
"""
from __future__ import annotations

from typing import Any


def derive_aggregates(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate fields from case_results.

    Returns dict with: total_cases, passed, failed, pass_rate, avg_score.
    All values are concrete (never None).
    """
    total = len(case_results)
    if total == 0:
        return {
            "total_cases": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_score": 0.0,
        }
    passed = sum(1 for c in case_results if c.get("passed"))
    scores = [float(c.get("score", 0.0) or 0.0) for c in case_results]
    return {
        "total_cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 3),
        "avg_score": round(sum(scores) / total, 3),
    }


def ensure_aggregates(record: dict[str, Any]) -> dict[str, Any]:
    """Ensure a run record has top-level aggregate fields.

    If top-level fields (passed_cases, total_cases, pass_rate, avg_score,
    failed_cases) are missing/None, derives them from summary or case_results.
    Never overwrites present non-None values.

    Returns the same dict, mutated in place for convenience.
    """
    summary = record.get("summary") or {}
    cases = record.get("case_results") or []

    # Derive from case_results if summary is also missing
    derived = derive_aggregates(cases) if cases else None

    def _get(key: str, summary_key: str | None = None) -> Any:
        """Resolve from summary first, then derived."""
        val = summary.get(summary_key or key)
        if val is not None:
            return val
        if derived:
            return derived.get(key)
        return 0

    fields = {
        "pass_rate": _get("pass_rate"),
        "avg_score": _get("avg_score"),
        "total_cases": _get("total_cases"),
        "passed_cases": _get("passed", "passed"),
        "failed_cases": _get("failed", "failed"),
    }

    for k, v in fields.items():
        if record.get(k) is None:
            record[k] = v

    return record
