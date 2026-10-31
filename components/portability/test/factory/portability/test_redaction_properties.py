"""Property tests for the redaction guard — arbitrary content must never
carry a known secret shape through unscrubbed."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.portability.runtime.redaction import scrub, still_trips
from factory.portability.runtime.bundle_models import identity_of, sha256_hex


@given(text=st.text(max_size=500))
@settings(max_examples=100)
def test_scrub_never_raises_on_arbitrary_text(text):
    scrub(text)  # must not raise regardless of input shape


@given(prefix=st.text(max_size=50), suffix=st.text(max_size=50))
@settings(max_examples=50)
def test_a_planted_akia_key_never_survives_scrubbing(prefix, suffix):
    planted = f"{prefix}AKIA1234567890ABCDEF{suffix}"
    scrubbed = scrub(planted)
    assert "AKIA1234567890ABCDEF" not in scrubbed


@given(prefix=st.text(max_size=50), token=st.text(min_size=20, max_size=40, alphabet=st.characters(min_codepoint=97, max_codepoint=122)))
@settings(max_examples=50)
def test_a_planted_sk_style_token_never_survives_scrubbing(prefix, token):
    planted = f"{prefix}sk-{token}"
    scrubbed = scrub(planted)
    assert f"sk-{token}" not in scrubbed


@given(namespace=st.text(min_size=1, max_size=30), key=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_identity_of_is_deterministic_and_64_hex(namespace, key):
    first = identity_of(namespace, key)
    second = identity_of(namespace, key)
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


@given(namespace=st.text(min_size=1, max_size=30), key_a=st.text(min_size=1, max_size=50), key_b=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_identity_of_differs_for_different_keys(namespace, key_a, key_b):
    if key_a != key_b:
        assert identity_of(namespace, key_a) != identity_of(namespace, key_b)


@given(text=st.text(max_size=200))
@settings(max_examples=50)
def test_sha256_hex_is_deterministic(text):
    assert sha256_hex(text) == sha256_hex(text)
