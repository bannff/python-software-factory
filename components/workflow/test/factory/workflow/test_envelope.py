from __future__ import annotations

import pytest

from factory.workflow.runtime.envelope import parse_envelope


def test_parse_envelope_defaults() -> None:
    env = parse_envelope(None)
    assert env.attributes == {}


def test_parse_envelope_rejects_non_mapping() -> None:
    with pytest.raises(ValueError):
        parse_envelope([])  # type: ignore[arg-type]


def test_envelope_rejects_too_many_attributes() -> None:
    attrs = {f"k{i}": i for i in range(100)}
    with pytest.raises(Exception):
        parse_envelope({"attributes": attrs})
