"""Focused identity and severity semantics for the pytest debt ratchet."""

from __future__ import annotations

import pytest

from factory.test.interface import TestRuntime as Runtime
from factory.test.runtime.junit_fixtures import case, write_report


def compare(tmp_path, base_cases, candidate_cases):
    base = write_report(tmp_path / "base.xml", *base_cases)
    candidate = write_report(tmp_path / "candidate.xml", *candidate_cases)
    return Runtime(adapter_type="memory").compare_junit(base, candidate)


def test_unchanged_debt_is_legacy_and_exact_pass_is_resolved(tmp_path) -> None:
    result = compare(
        tmp_path,
        [case("test_legacy", "failure"), case("test_fixed", "error", phase="setup")],
        [case("test_legacy", "failure"), case("test_fixed")],
    )
    assert result["passed"] is True
    assert [item["reason"] for item in result["legacy"]] == ["unchanged_debt"]
    assert [item["reason"] for item in result["resolved"]] == ["executed_and_passed"]


def test_new_debt_blocks_without_aggregate_offset(tmp_path) -> None:
    result = compare(
        tmp_path,
        [case("test_old", "failure")],
        [case("test_old"), case("test_new", "failure")],
    )
    assert result["passed"] is False
    assert result["resolved"]
    assert result["blocking"][0]["reason"] == "new_debt"


@pytest.mark.parametrize("outcome", ["skipped", "xfail"])
def test_suppressing_baseline_debt_blocks(tmp_path, outcome) -> None:
    result = compare(tmp_path, [case("test_debt", "failure")], [case("test_debt", outcome)])
    assert result["passed"] is False
    assert result["blocking"][0]["reason"] == "baseline_debt_suppressed"


def test_missing_or_deselected_baseline_debt_blocks(tmp_path) -> None:
    result = compare(tmp_path, [case("test_debt", "failure")], [case("test_other")])
    assert result["blocking"][0]["reason"] == "baseline_debt_missing"


def test_failure_to_error_blocks_but_error_to_failure_is_legacy(tmp_path) -> None:
    worse = compare(tmp_path, [case("test_debt", "failure")], [case("test_debt", "error")])
    better = compare(tmp_path, [case("test_debt", "error")], [case("test_debt", "failure")])
    assert worse["blocking"][0]["reason"] == "failure_to_error"
    assert better["passed"] is True
    assert better["legacy"][0]["reason"] == "error_to_failure"


def test_phase_change_is_new_debt_and_does_not_resolve_old_phase(tmp_path) -> None:
    result = compare(
        tmp_path,
        [case("test_debt", "error", phase="setup")],
        [case("test_debt", "error", phase="teardown")],
    )
    assert result["passed"] is False
    assert {item["reason"] for item in result["blocking"]} == {
        "new_debt", "baseline_debt_not_passed"
    }


def test_collection_debt_is_evidence_bound_and_candidate_fails_closed(tmp_path) -> None:
    base_fixed = compare(
        tmp_path,
        [case("test_collect", "error", phase="collection")],
        [case("test_collect")],
    )
    candidate_broken = compare(
        tmp_path,
        [case("test_collect")],
        [case("test_collect", "error", phase="collection")],
    )
    symmetric = compare(
        tmp_path,
        [case("test_collect", "error", phase="collection")],
        [case("test_collect", "error", phase="collection")],
    )
    assert base_fixed["passed"] is True
    assert base_fixed["resolved"][0]["reason"] == "collection_executed_and_passed"
    assert candidate_broken["blocking"][0]["reason"] == "candidate_incomplete_collection"
    assert len(symmetric["blocking"]) == 1
    assert symmetric["blocking"][0] == {
        "identity": symmetric["blocking"][0]["identity"],
        "phase": "collection", "baseline_outcome": "error",
        "candidate_outcome": "error", "reason": "candidate_incomplete_collection",
    }


def test_baseline_collection_requires_nonempty_all_pass_same_file(tmp_path) -> None:
    missing = compare(
        tmp_path,
        [case("test_collect", "error", phase="collection")],
        [case("test_other", file="components/other/test_unit.py")],
    )
    mixed = compare(
        tmp_path,
        [case("test_collect", "error", phase="collection")],
        [case("test_one"), case("test_two", "failure")],
    )
    assert missing["blocking"][0]["candidate_outcome"] == "missing"
    assert mixed["blocking"][0]["candidate_outcome"] == "mixed"


def test_invalid_report_returns_explicit_block(tmp_path) -> None:
    base = tmp_path / "base.xml"
    base.write_text("bad", encoding="utf-8")
    candidate = write_report(tmp_path / "candidate.xml", case("test_ok"))
    result = Runtime(adapter_type="memory").compare_junit(str(base), candidate)
    assert result["passed"] is False
    assert result["errors"]
    assert result["blocking"][0]["reason"] == "invalid_report"


def test_passing_baseline_cannot_be_suppressed_or_removed(tmp_path) -> None:
    skipped = compare(tmp_path, [case("test_required")], [case("test_required", "skipped")])
    missing = compare(tmp_path, [case("test_required")], [case("test_other")])
    assert skipped["blocking"][0]["reason"] == "baseline_pass_suppressed"
    assert missing["blocking"][0]["reason"] == "baseline_pass_missing"
