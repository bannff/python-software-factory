"""Tests for the shared make_serializable utility."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from factory.mcp_utils.serialization import make_serializable


class Color(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class Point:
    x: int
    y: int


def test_primitives_pass_through():
    assert make_serializable(None) is None
    assert make_serializable(42) == 42
    assert make_serializable("hello") == "hello"
    assert make_serializable(True) is True


def test_enum_returns_value():
    assert make_serializable(Color.RED) == "red"


def test_datetime_returns_isoformat():
    dt = datetime.datetime(2025, 1, 15, 12, 0, 0)
    assert make_serializable(dt) == "2025-01-15T12:00:00"


def test_bytes_decoded():
    assert make_serializable(b"hello") == "hello"


def test_dataclass_converted():
    result = make_serializable(Point(1, 2))
    assert result == {"x": 1, "y": 2}


def test_nested_dict():
    data = {"color": Color.BLUE, "point": Point(3, 4)}
    result = make_serializable(data)
    assert result == {"color": "blue", "point": {"x": 3, "y": 4}}


def test_list_and_set():
    assert make_serializable([1, Color.RED]) == [1, "red"]
    assert make_serializable({1, 2}) == [1, 2] or set(make_serializable({1, 2})) == {1, 2}


def test_pydantic_model_dump():
    """Objects with model_dump() are serialized via that method."""
    class FakeModel:
        def model_dump(self):
            return {"a": 1}
    assert make_serializable(FakeModel()) == {"a": 1}


def test_fallback_to_str():
    class Custom:
        def __str__(self):
            return "custom-obj"
    assert make_serializable(Custom()) == "custom-obj"
