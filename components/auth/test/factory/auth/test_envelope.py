from __future__ import annotations

import pytest

from factory.auth.runtime.envelope import parse_envelope


def test_envelope_defaults() -> None:
    env = parse_envelope(None)
    assert env.attributes == {}
    assert env.timestamp is not None


def test_envelope_rejects_too_many_attributes() -> None:
    too_many = {f"k{i}": True for i in range(65)}
    with pytest.raises(Exception):
        _ = parse_envelope({"attributes": too_many})


def test_envelope_rejects_long_value() -> None:
    with pytest.raises(Exception):
        _ = parse_envelope({"attributes": {"k": "x" * 600}})
