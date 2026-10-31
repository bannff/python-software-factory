"""Model contract tests for the domain brick (bd:python-factory-w7i8k).

Verifies the charset REJECT-not-coerce rule and ``extra="forbid"`` on
every model. Behaviour only — no internals.

Properties:
  * ``domain_id`` / ``Engagement.id`` charset: lowercase alnum + ``-``/``_``,
    first char alnum. Uppercase / spaces / leading punctuation are REJECTED
    (raise ValidationError) — NEVER silently lowercased/coerced.
  * Valid lowercase ids round-trip.
  * ``extra="forbid"`` on PresentationManifest / TypeDescriptor /
    ThemeAccents / Engagement.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from factory.domain.runtime.models import (
    Engagement,
    PresentationManifest,
    ThemeAccents,
    TypeDescriptor,
)

# A charset-valid id: first char lowercase-alnum, rest lowercase-alnum/-/_.
_VALID_ID = st.from_regex(r"\A[a-z0-9][a-z0-9_-]{0,30}\Z", fullmatch=True)


@settings(max_examples=50)
@given(domain_id=_VALID_ID)
def test_valid_domain_id_accepted(domain_id: str) -> None:
    """Valid lowercase ids pass and round-trip unchanged."""
    m = PresentationManifest(domain_id=domain_id)
    assert m.domain_id == domain_id


@settings(max_examples=50)
@given(domain_id=_VALID_ID)
def test_valid_engagement_id_accepted(domain_id: str) -> None:
    """Valid Engagement.id passes; domain_id field is charset-locked too."""
    e = Engagement(id=domain_id, domain_id=domain_id)
    assert e.id == domain_id


def test_manifest_rejects_uppercase_not_coerce() -> None:
    """``Security`` is REJECTED, not coerced to ``security``."""
    with pytest.raises(ValidationError):
        PresentationManifest(domain_id="Security")


def test_engagement_rejects_whitespace_id() -> None:
    """``Bad Id`` (space) is rejected at Engagement.id."""
    with pytest.raises(ValidationError):
        Engagement(id="Bad Id", domain_id="x")


@settings(max_examples=50)
@given(
    bad=st.sampled_from(
        ["Security", "ABC", "has space", "-leading", "_leading", "" , "café"]
    )
)
def test_charset_rejects_invalid_ids(bad: str) -> None:
    """Uppercase / space / leading punct / empty / non-ascii are rejected."""
    with pytest.raises(ValidationError):
        PresentationManifest(domain_id=bad)


def test_manifest_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        PresentationManifest(domain_id="x", system_prompt="nope")


def test_type_descriptor_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        TypeDescriptor(label="x", bogus="nope")


def test_theme_accents_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        ThemeAccents(primary="#000", bogus="nope")


def test_engagement_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Engagement(id="x", domain_id="x", bogus="nope")


def test_manifest_only_domain_id_required() -> None:
    """Generic-by-default: domain_id is the only required field."""
    m = PresentationManifest(domain_id="x")
    assert m.labels == {}
    assert m.type_descriptors == {}
    assert m.theme is None
    assert m.default_persona_id is None
