"""Tests for deterministic GT scorer — P/R/F1 computation.

Covers default DAST behavior, SAST mode (``match_on=("cwe","file")``),
narrow DAST (``match_on=("cwe","method","path")``), eligibility rules,
match_on edge cases, and a Hypothesis purity property.
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.evals.runtime.gt_scorer import score, _normalize_path


GT = [
    {"gt_id": "g1", "cwe": "CWE-639", "artifact": {"method": "GET", "path": "/users/{id}"}},
    {"gt_id": "g2", "cwe": "CWE-639", "artifact": {"method": "DELETE", "path": "/users/{id}"}},
    {"gt_id": "g3", "cwe": "CWE-89", "artifact": {"method": "GET", "path": "/debug"}},
]


def test_perfect_match():
    findings = [
        {"cwe": "CWE-639", "method": "GET", "path": "/users/{id}"},
        {"cwe": "CWE-639", "method": "DELETE", "path": "/users/<id>"},
        {"cwe": "CWE-89", "method": "GET", "path": "/debug"},
    ]
    r = score(findings, GT)
    assert (r["precision"], r["recall"], r["f1"]) == (1.0, 1.0, 1.0)
    assert r["true_positives"] == 3


def test_partial_match():
    r = score([{"cwe": "CWE-639", "method": "GET", "path": "/users/{x}"}], GT)
    assert r["true_positives"] == 1
    assert r["false_negatives"] == 2
    assert r["recall"] == round(1 / 3, 4)


def test_no_match():
    r = score([{"cwe": "CWE-79", "method": "POST", "path": "/xss"}], GT)
    assert r["true_positives"] == 0
    assert r["false_positives_count"] == 1
    assert r["false_negatives"] == 3


def test_empty_findings():
    r = score([], GT)
    assert r["recall"] == 0.0
    assert r["false_negatives"] == 3


def test_empty_gt():
    r = score([{"cwe": "CWE-639", "method": "GET", "path": "/x"}], [])
    assert r["precision"] == 0.0
    assert r["false_positives_count"] == 1


def test_path_normalization():
    assert _normalize_path("/users/{id}") == "/users/{param}"
    assert _normalize_path("/users/<id>") == "/users/{param}"
    assert _normalize_path("/users/:id") == "/users/{param}"
    assert _normalize_path("/USERS/{ID}/") == "/users/{param}"


def test_resource_string_method_extraction():
    r = score([{"cwe": "CWE-639", "resource": "GET /users/{id}"}], GT)
    assert r["true_positives"] == 1


def test_duplicate_findings():
    findings = [
        {"cwe": "CWE-639", "method": "GET", "path": "/users/{a}"},
        {"cwe": "CWE-639", "method": "GET", "path": "/users/:b}"},
    ]
    r = score(findings, GT)
    assert r["true_positives"] == 1
    assert r["false_positives_count"] == 1


def test_sast_match_by_cwe_and_file_basename():
    findings = [
        {"cwe": "CWE-89", "file": "/repo/app/db.py"},
        {"cwe": "CWE-79", "file": "/repo/app/views.py"},
    ]
    gt = [
        {"gt_id": "s1", "cwe": "CWE-89",
         "code_evidence": {"locations": [{"file": "/code/db.py", "line": 12}]}},
        {"gt_id": "s2", "cwe": "CWE-22",
         "code_evidence": {"locations": [{"file": "/code/views.py"}]}},
    ]
    r = score(findings, gt, match_on=("cwe", "file"))
    assert (r["true_positives"], r["false_positives_count"], r["false_negatives"]) == (1, 1, 1)


def test_sast_match_falls_back_to_top_level_file():
    findings = [{"cwe": "CWE-89", "file": "src/auth/login.py"}]
    gt = [{"gt_id": "s1", "cwe": "CWE-89", "file": "auth/login.py"}]
    assert score(findings, gt, match_on=("cwe", "file"))["true_positives"] == 1


def test_dast_narrow_ignores_file_field():
    findings = [{"cwe": "CWE-639", "method": "GET", "path": "/users/{x}",
                 "file": "/sast-noise/users.py"}]
    r = score(findings, GT, match_on=("cwe", "method", "path"))
    assert r["true_positives"] == 1


def test_sast_file_key_actually_discriminates_same_cwe():
    """Guard against typo'd file-extractor key: same-CWE pair with different
    files MUST yield 2 distinct matches, not 1."""
    findings = [
        {"cwe": "CWE-89", "file": "/repo/db.py"},
        {"cwe": "CWE-89", "file": "/repo/views.py"},
    ]
    gt = [
        {"gt_id": "s1", "cwe": "CWE-89", "file": "/code/db.py"},
        {"gt_id": "s2", "cwe": "CWE-89", "file": "/code/views.py"},
    ]
    assert score(findings, gt, match_on=("cwe", "file"))["true_positives"] == 2


def test_match_on_with_unknown_key_is_graceful():
    """Unknown key extracts to None → "" on both sides → entries still match."""
    findings = [{"cwe": "CWE-89", "method": "GET", "path": "/x"}]
    gt = [{"cwe": "CWE-89", "artifact": {"method": "GET", "path": "/x"}}]
    r = score(findings, gt, match_on=("cwe", "nonexistent"))
    assert (r["true_positives"], r["false_positives_count"]) == (1, 0)


def test_match_on_empty_tuple_matches_nothing():
    """An explicit empty matcher is strict-empty, not the default matcher."""
    findings = [{"cwe": "CWE-639", "method": "GET", "path": "/users/{id}"}]
    result = score(findings, GT, match_on=())
    assert result["true_positives"] == 0
    assert result["false_positives_count"] == 1
    assert result["false_negatives"] == 0


def test_match_on_single_key_cwe_only():
    """``match_on=("cwe",)`` ignores method+path."""
    findings = [{"cwe": "CWE-89", "method": "POST", "path": "/elsewhere"}]
    gt = [{"cwe": "CWE-89", "artifact": {"method": "GET", "path": "/different"}}]
    assert score(findings, gt, match_on=("cwe",))["true_positives"] == 1


def test_finding_missing_all_match_keys_is_false_positive():
    r = score([{"description": "nothing"}], GT, match_on=("cwe", "method", "path"))
    assert r["true_positives"] == 0
    assert r["false_positives_count"] == 1


def test_gt_missing_all_match_keys_is_skipped_not_missed():
    gt = [
        {"gt_id": "ineligible", "description": "no fields"},
        {"gt_id": "g3", "cwe": "CWE-89", "artifact": {"method": "GET", "path": "/debug"}},
    ]
    findings = [{"cwe": "CWE-89", "method": "GET", "path": "/debug"}]
    r = score(findings, gt, match_on=("cwe", "method", "path"))
    assert r["true_positives"] == 1
    assert r["false_negatives"] == 0


_finding_st = st.fixed_dictionaries({
    "cwe": st.sampled_from(["CWE-89", "CWE-79", "CWE-639", "639", ""]),
    "method": st.sampled_from(["GET", "POST", "DELETE", ""]),
    "path": st.sampled_from(["/users/{id}", "/debug", "/x", ""]),
    "file": st.sampled_from(["/repo/db.py", "views.py", ""]),
})
_gt_st = st.fixed_dictionaries({
    "gt_id": st.text(min_size=1, max_size=8),
    "cwe": st.sampled_from(["CWE-89", "CWE-639", "CWE-22"]),
    "artifact": st.fixed_dictionaries({
        "method": st.sampled_from(["GET", "DELETE", "POST"]),
        "path": st.sampled_from(["/users/{id}", "/debug", "/x"]),
    }),
})


@given(findings=st.lists(_finding_st, max_size=10),
       gt_entries=st.lists(_gt_st, max_size=10))
@settings(max_examples=50)
def test_score_is_pure_deterministic(findings, gt_entries):
    a = score(findings, gt_entries)
    b = score(findings, gt_entries)
    assert (a["precision"], a["recall"], a["f1"]) == (b["precision"], b["recall"], b["f1"])
    tp, fp, fn = a["true_positives"], a["false_positives_count"], a["false_negatives"]
    assert (tp, fp, fn) == (b["true_positives"], b["false_positives_count"], b["false_negatives"])
    # Algebra invariants
    assert tp + fp == len(findings)  # every finding is matched or FP
    assert len({id(m["finding"]) for m in a["matched"]}) == tp  # no double-counting
    eligible = sum(
        1 for g in gt_entries
        if g.get("cwe") or (g.get("artifact") or {}).get("method")
        or (g.get("artifact") or {}).get("path")
    )
    assert tp + fn <= eligible
