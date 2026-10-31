"""Cypher-injection guard for ``MemoryQuery.metadata`` keys.

bd:python-factory-b2d2o (epic python-factory-hadbi). Meta-architect
verdict f279063c Q7-SECURITY: Cypher property names cannot be
parameterised, so a key like ``"x; MATCH (n) DETACH DELETE n; //"``
would be Cypher injection. Defense-in-depth at TWO sites:

K9  Pydantic ``MemoryQuery.metadata`` ``field_validator`` — fires at
    contract construction.
K10 Adapter-side ``factory.memory.runtime.adapters._neo4j_filters
    .safe_property_key`` — fires inside the Cypher builder, even if a
    caller bypasses ``MemoryQuery``.

Precedent: ``components/graph/.../runtime/adapters/_neo4j_finding.py
::safe_label``.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.memory.runtime.adapters._neo4j_filters import (
    safe_property_key as adapter_safe,
)
from factory.memory.runtime.models import (
    MemoryQuery,
    safe_property_key as model_safe,
)


_GOOD = ["a", "_x", "X", "abc_123", "_", "run_id", "agent_id"]
_BAD = [
    "1abc",
    "a-b",
    "a.b",
    "a b",
    "",
    "a;b",
    "x; MATCH (n) DETACH DELETE n; //",
    "1leading-digit",
    "with space",
    "with.dot",
    "x'; DROP TABLE",
]


# -- K9 — Pydantic field_validator (contract-level guard) --


class TestPydanticFieldValidator:
    @pytest.mark.parametrize("evil_key", _BAD)
    def test_validator_rejects_unsafe_keys(self, evil_key: str) -> None:
        with pytest.raises(ValidationError):
            MemoryQuery(user_id="u", query="x", metadata={evil_key: "v"})

    def test_safe_keys_round_trip(self) -> None:
        """Sanity: legit lineage keys pass."""
        q = MemoryQuery(
            user_id="u", query="x",
            metadata={
                "run_id": "r-1", "agent_id": "a", "target_app": "billing",
            },
        )
        assert q.metadata == {
            "run_id": "r-1", "agent_id": "a", "target_app": "billing",
        }

    def test_metadata_none_does_not_trip_validator(self) -> None:
        q = MemoryQuery(user_id="u", query="x", metadata=None)
        assert q.metadata is None

    def test_metadata_empty_does_not_trip_validator(self) -> None:
        q = MemoryQuery(user_id="u", query="x", metadata={})
        assert q.metadata == {}


# -- K10 — adapter-side safe_property_key (defense-in-depth) --


class TestSafePropertyKeyDirect:
    @pytest.mark.parametrize("good", _GOOD)
    def test_model_helper_accepts_safe_keys(self, good: str) -> None:
        assert model_safe(good) == good

    @pytest.mark.parametrize("good", _GOOD)
    def test_adapter_helper_accepts_safe_keys(self, good: str) -> None:
        assert adapter_safe(good) == good

    @pytest.mark.parametrize("bad", _BAD)
    def test_model_helper_rejects_unsafe_keys(self, bad: str) -> None:
        with pytest.raises(ValueError):
            model_safe(bad)

    @pytest.mark.parametrize("bad", _BAD)
    def test_adapter_helper_rejects_unsafe_keys(self, bad: str) -> None:
        with pytest.raises(ValueError):
            adapter_safe(bad)

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ValueError):
            model_safe(42)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            adapter_safe(42)  # type: ignore[arg-type]

    def test_model_and_adapter_agree(self) -> None:
        """Both helpers must enforce the same regex (defense-in-depth
        only protects when the two ends agree)."""
        for good in _GOOD:
            assert model_safe(good) == adapter_safe(good)


# -- Hypothesis: any unsafe codepoint must fail --


_UNSAFE_INTRO = st.sampled_from(
    list(" \t\n;-.()'\"/\\,#$%^&*=+:|<>?!{}[]~`@"),
)
_SAFE_TAIL = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    ),
    min_size=0, max_size=6,
)


@settings(max_examples=40, deadline=None)
@given(intro=_UNSAFE_INTRO, tail=_SAFE_TAIL)
def test_any_unsafe_char_anywhere_rejected(intro: str, tail: str) -> None:
    """Property: any non-``[a-zA-Z0-9_]`` char anywhere in the key
    rejects, both at the model boundary and the adapter boundary."""
    candidate = "a" + intro + tail  # leading 'a' so digit-leading isn't the cause
    with pytest.raises(ValueError):
        model_safe(candidate)
    with pytest.raises(ValueError):
        adapter_safe(candidate)


# -- bd:python-factory-b2d2o QA wave: trailing-anchor bypass (deterministic) --
#
# Python's ``re`` module treats ``$`` as "end of string OR before a single
# trailing newline" by default. The ``^[a-zA-Z_][a-zA-Z0-9_]*$`` regex therefore
# accepts ``"a\n"`` and any other key whose only unsafe char is a trailing
# newline — silently letting it land in the Cypher fragment as
# ``m.meta_a\n = $meta_a\n``.  The Hypothesis canary above catches this only
# when the ``\n`` example is drawn early; this deterministic case pins it.
#
# Defense: switch to ``re.fullmatch`` or anchor with ``\Z`` instead of ``$``
# (or ``re.compile(..., flags=re.MULTILINE)`` is NOT the fix — it makes
# things worse).
_TRAILING_BYPASS = ["a\n", "run_id\n", "agent_id\r", "x\t", "x\v", "x\f"]


@pytest.mark.parametrize("evil_key", _TRAILING_BYPASS)
def test_trailing_whitespace_or_newline_rejected_at_model(evil_key: str) -> None:
    """Trailing ``\\n``/``\\r``/``\\t``/etc must reject — Python ``$`` anchor
    by default accepts a single trailing newline (bd:python-factory-b2d2o
    QA finding)."""
    with pytest.raises(ValueError):
        model_safe(evil_key)


@pytest.mark.parametrize("evil_key", _TRAILING_BYPASS)
def test_trailing_whitespace_or_newline_rejected_at_adapter(evil_key: str) -> None:
    with pytest.raises(ValueError):
        adapter_safe(evil_key)


@pytest.mark.parametrize("evil_key", _TRAILING_BYPASS)
def test_trailing_whitespace_or_newline_rejected_at_pydantic(evil_key: str) -> None:
    """K9 boundary — MemoryQuery validator must reject too."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MemoryQuery(user_id="u", query="x", metadata={evil_key: "v"})
