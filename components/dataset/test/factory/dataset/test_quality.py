"""Tests for dataset quality evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.dataset.runtime.quality import evaluate_quality


@dataclass
class _Msg:
    role: str
    content: str


@dataclass
class _Record:
    messages: list[_Msg] = field(default_factory=list)


def _record(*roles_and_content: tuple[str, str]) -> _Record:
    return _Record(messages=[_Msg(role=r, content=c) for r, c in roles_and_content])


def test_happy_path_passes() -> None:
    records = [
        _record(("user", "hello"), ("assistant", "hi")),
        _record(("user", "bye"), ("assistant", "goodbye")),
    ]
    result = evaluate_quality(records)
    assert result.passed is True
    assert result.checks["schema"] == "passed"
    assert result.checks["empty_messages"] == "passed"
    assert result.checks["role_coverage"] == "passed"
    assert result.checks["duplicate_detection"] == "passed"
    assert result.checks["record_count"] == "passed: 2"


def test_empty_messages_detected() -> None:
    records = [_record(("user", ""), ("assistant", "hi"))]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "failed" in result.checks["empty_messages"]


def test_record_with_no_messages_detected() -> None:
    records = [_Record(messages=[])]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "failed" in result.checks["empty_messages"]


def test_missing_user_role_detected() -> None:
    records = [_record(("assistant", "hi"))]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "user" in result.checks["role_coverage"]


def test_missing_assistant_role_detected() -> None:
    records = [_record(("user", "hi"))]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "assistant" in result.checks["role_coverage"]


def test_duplicate_detection_warns() -> None:
    rec = _record(("user", "same"), ("assistant", "same"))
    result = evaluate_quality([rec, rec])
    assert result.passed is True
    assert "warn" in result.checks["duplicate_detection"]
    assert "1 duplicates" in result.checks["duplicate_detection"]


def test_max_message_length_violation() -> None:
    long_content = "x" * 100_001
    records = [_record(("user", long_content), ("assistant", "ok"))]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "failed" in result.checks["max_message_length"]


def test_empty_record_list() -> None:
    result = evaluate_quality([])
    assert result.passed is False
    assert result.checks["record_count"] == "failed: 0 records"
    assert result.checks["empty_messages"] == "passed"
    assert result.checks["role_coverage"] == "passed"


def test_record_with_raw_dict_messages_detected() -> None:
    records = [
        {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
    ]
    result = evaluate_quality(records)
    assert result.passed is True
    assert result.checks["record_count"] == "passed: 1"


def test_record_missing_messages_attr_fails_schema() -> None:
    records = [{"not_messages": []}]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "failed" in result.checks["schema"]


def test_both_roles_missing() -> None:
    records = [_record(("system", "system prompt"))]
    result = evaluate_quality(records)
    assert result.passed is False
    assert "user" in result.checks["role_coverage"]
    assert "assistant" in result.checks["role_coverage"]


def test_multiple_empty_messages_aggregate() -> None:
    records = [
        _record(("user", ""), ("assistant", "ok")),
        _record(("user", ""), ("assistant", "ok")),
    ]
    result = evaluate_quality(records)
    assert "2 empty messages" in result.checks["empty_messages"]


@given(
    n=st.integers(min_value=0, max_value=50),
    roles=st.lists(
        st.sampled_from(["user", "assistant"]),
        min_size=1,
        max_size=5,
    ),
)
@settings(max_examples=200)
def test_output_always_has_expected_keys(n: int, roles: list[str]) -> None:
    records = [
        _Record(
            messages=[_Msg(role=r, content=f"msg-{i}-{r}") for i, r in enumerate(roles)]
        )
        for _ in range(n)
    ]
    result = evaluate_quality(records)
    assert isinstance(result.checks, dict)
    expected_keys = {
        "record_count",
        "schema",
        "empty_messages",
        "role_coverage",
        "duplicate_detection",
        "max_message_length",
    }
    assert set(result.checks.keys()) == expected_keys
    assert isinstance(result.passed, bool)
