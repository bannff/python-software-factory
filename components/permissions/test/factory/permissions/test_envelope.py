from __future__ import annotations

import pytest

from factory.permissions.runtime.envelope import Envelope


def test_attributes_limits() -> None:
    env = Envelope(attributes={"k": "v"})
    assert env.attributes["k"] == "v"

    with pytest.raises(ValueError):
        _ = Envelope(attributes={"": "x"})


def test_attribute_key_too_long() -> None:
    with pytest.raises(ValueError):
        _ = Envelope(attributes={"k" * 65: "v"})


def test_attribute_value_too_long() -> None:
    with pytest.raises(ValueError):
        _ = Envelope(attributes={"k": "v" * 513})
