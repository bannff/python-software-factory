"""Identity-based pytest debt comparison."""

from __future__ import annotations

from pathlib import Path

from .junit_models import DEBT_OUTCOMES, JUnitCase, JUnitComparison, JUnitReport
from .junit_parser import JUnitReportError, parse_junit_report


def _entry(
    case: JUnitCase,
    reason: str,
    baseline: str = "absent",
    candidate: str = "absent",
) -> dict[str, str]:
    return {
        "identity": case.identity,
        "phase": case.phase,
        "baseline_outcome": baseline,
        "candidate_outcome": candidate,
        "reason": reason,
    }


def _collection_passed(base_case: JUnitCase, candidate: JUnitReport) -> bool:
    if base_case.phase != "collection" or not base_case.file:
        return False
    same_file = [case for case in candidate.cases if case.file == base_case.file]
    return bool(same_file) and all(case.outcome == "passed" for case in same_file)


def _file_outcome(base_case: JUnitCase, candidate: JUnitReport) -> str:
    same_file = [case.outcome for case in candidate.cases if case.file == base_case.file]
    if not same_file:
        return "missing"
    outcomes = set(same_file)
    return next(iter(outcomes)) if len(outcomes) == 1 else "mixed"


def compare_reports(base: JUnitReport, candidate: JUnitReport) -> JUnitComparison:
    """Compare validated reports without allowing aggregate debt offsets."""
    result = JUnitComparison(base=base.summary(), candidate=candidate.summary())
    base_collection = {
        case.identity: case for case in base.cases
        if case.phase == "collection" and case.outcome in DEBT_OUTCOMES
    }
    candidate_collection = {
        case.identity: case for case in candidate.cases
        if case.phase == "collection" and case.outcome in DEBT_OUTCOMES
    }
    for identity, case in sorted(candidate_collection.items()):
        prior = base_collection.get(identity)
        result.blocking.append(_entry(
            case, "candidate_incomplete_collection",
            prior.outcome if prior is not None else "absent", case.outcome,
        ))
    for identity, case in sorted(base_collection.items()):
        if identity in candidate_collection:
            continue
        if _collection_passed(case, candidate):
            result.resolved.append(_entry(
                case, "collection_executed_and_passed", case.outcome, "passed",
            ))
        else:
            result.blocking.append(_entry(
                case, "base_incomplete_collection", case.outcome,
                _file_outcome(case, candidate),
            ))
    base_debt = {
        case.debt_key: case
        for case in base.cases
        if case.outcome in DEBT_OUTCOMES and case.phase != "collection"
    }
    candidate_debt = {
        case.debt_key: case
        for case in candidate.cases
        if case.outcome in DEBT_OUTCOMES and case.phase != "collection"
    }
    candidate_cases = {case.identity: case for case in candidate.cases}
    for case in base.cases:
        if case.outcome != "passed":
            continue
        current = candidate_cases.get(case.identity)
        if current is None:
            result.blocking.append(_entry(
                case, "baseline_pass_missing", "passed", "missing",
            ))
        elif current.outcome in {"skipped", "xfail"}:
            result.blocking.append(_entry(
                case, "baseline_pass_suppressed", "passed", current.outcome,
            ))

    for key, case in sorted(candidate_debt.items()):
        prior = base_debt.get(key)
        if prior is None:
            result.blocking.append(_entry(case, "new_debt", candidate=case.outcome))
        elif prior.outcome == "failure" and case.outcome == "error":
            result.blocking.append(
                _entry(case, "failure_to_error", prior.outcome, case.outcome)
            )
        else:
            reason = (
                "error_to_failure"
                if prior.outcome == "error" and case.outcome == "failure"
                else "unchanged_debt"
            )
            result.legacy.append(_entry(case, reason, prior.outcome, case.outcome))

    for key, case in sorted(base_debt.items()):
        if key in candidate_debt:
            continue
        current = candidate_cases.get(case.identity)
        if current is not None and current.outcome == "passed":
            result.resolved.append(_entry(case, "executed_and_passed", case.outcome, "passed"))
            continue
        if current is None:
            reason, outcome = "baseline_debt_missing", "missing"
        elif current.outcome in {"skipped", "xfail"}:
            reason, outcome = "baseline_debt_suppressed", current.outcome
        else:
            reason, outcome = "baseline_debt_not_passed", current.outcome
        result.blocking.append(_entry(case, reason, case.outcome, outcome))

    result.passed = not result.blocking
    return result


def compare_junit_reports(
    base_path: str | Path, candidate_path: str | Path, *, nofollow: bool = False
) -> JUnitComparison:
    """Parse and compare two reports, returning an explicit fail-closed result."""
    try:
        base = parse_junit_report(base_path, nofollow=nofollow)
        candidate = parse_junit_report(candidate_path, nofollow=nofollow)
    except JUnitReportError as exc:
        return JUnitComparison(errors=[str(exc)], blocking=[{
            "identity": "<report>",
            "phase": "collection",
            "baseline_outcome": "unknown",
            "candidate_outcome": "unknown",
            "reason": "invalid_report",
        }])
    return compare_reports(base, candidate)
