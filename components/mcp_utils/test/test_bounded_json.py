"""Exact boundary coverage for shared bounded JSON evidence."""

from datetime import datetime, timezone

from factory.mcp_utils.interface import is_bounded_json
from factory.mcp_utils.runtime.bounded_json import to_plain_json


def test_bounded_json_accepts_and_rejects_exact_limits() -> None:
    assert is_bounded_json({"text": "x" * 65_536})
    assert not is_bounded_json({"text": "x" * 65_537})
    assert is_bounded_json({"number": 1_000_000_000})
    assert not is_bounded_json({"number": 1_000_000_001})
    assert is_bounded_json(list(range(1_024)))
    assert not is_bounded_json(list(range(1_025)))
    assert is_bounded_json({str(index): index for index in range(256)})
    assert not is_bounded_json({str(index): index for index in range(257)})


def test_bounded_json_nesting_limit_is_inclusive() -> None:
    value: object = "leaf"
    for _ in range(12):
        value = [value]
    assert is_bounded_json(value)
    value = [value]
    assert not is_bounded_json(value)


def test_to_plain_json_serializes_datetime_and_set_values() -> None:
    value = to_plain_json({
        "when": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "fields": {"b", "a"},
    })

    assert value == {
        "when": "2025-01-01T00:00:00+00:00",
        "fields": ["a", "b"],
    }
