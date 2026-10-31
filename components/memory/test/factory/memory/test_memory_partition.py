"""Owner-partitioned Memory namespace derivation (M6.5 slice 3).

Proves the Memory-owned partition seam: owner and scope validate separately,
the adapter ``user_id`` is derived exactly as ``sha256(owner).hexdigest() + "."
+ scope``, distinct owner/scope pairs never collide, delimiter-laden owners
cannot forge another partition, and empty/invalid/credential-shaped scopes fail
closed.
"""
from __future__ import annotations

import hashlib

import pytest
from hypothesis import given, settings, strategies as st

from factory.memory.interface import (
    derive_memory_user_id,
    validate_memory_scope,
    validate_owner_id,
)
from factory.memory.runtime.partition import SAFE_OWNER_ERROR, SAFE_SCOPE_ERROR

_SCOPES = st.from_regex(r"\A[a-z0-9][a-z0-9_-]{0,20}\Z", fullmatch=True)
# Owners deliberately include the '.' delimiter and other bytes the scope
# alphabet forbids, to prove they cannot leak across the fixed-width boundary.
_OWNERS = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=1, max_size=64,
)


def test_derivation_matches_exact_formula() -> None:
    digest = hashlib.sha256(b"owner-1").hexdigest()
    assert derive_memory_user_id("owner-1", "default") == f"{digest}.default"


@given(owner=_OWNERS, scope=_SCOPES)
@settings(max_examples=200)
def test_partition_key_shape_and_bound(owner: str, scope: str) -> None:
    key = derive_memory_user_id(owner, scope)
    digest, _, tail = key.partition(".")
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    assert tail == scope
    assert len(key) <= 256  # stays under the adapter user_id Field bound


@given(
    owner_a=_OWNERS, owner_b=_OWNERS, scope_a=_SCOPES, scope_b=_SCOPES,
)
@settings(max_examples=300)
def test_distinct_owner_scope_pairs_never_collide(
    owner_a: str, owner_b: str, scope_a: str, scope_b: str,
) -> None:
    key_a = derive_memory_user_id(owner_a, scope_a)
    key_b = derive_memory_user_id(owner_b, scope_b)
    same_pair = owner_a == owner_b and scope_a == scope_b
    assert (key_a == key_b) == same_pair


@given(owner=_OWNERS, scope=_SCOPES)
@settings(max_examples=200)
def test_delimiter_laden_owner_cannot_forge_another_partition(
    owner: str, scope: str,
) -> None:
    """A '.'-bearing owner cannot spoof ``<digest>.<other-scope>``.

    Owner is hashed to a fixed 64-hex prefix, so no owner string — however many
    dots it contains — can reproduce another owner's digest, and the scope
    alphabet excludes '.', so the boundary is unambiguous.
    """
    key = derive_memory_user_id(f"{owner}.{scope}", scope)
    honest = derive_memory_user_id(owner, scope)
    assert key != honest
    assert key.split(".")[0] != owner


@pytest.mark.parametrize(
    "scope",
    [
        "",  # empty
        " ",  # whitespace
        "default ",  # trailing space
        "Default",  # uppercase rejected
        "a.b",  # delimiter rejected
        "scope/../etc",  # path traversal shape
        "x" * 129,  # over the 128 bound
        "ghp_" + "a" * 36,  # GitHub token shape
        "sk-proj_" + "a" * 24,  # OpenAI key shape
        "xoxb-" + "a" * 20,  # Slack token shape
    ],
)
def test_invalid_or_credential_shaped_scope_fails_closed(scope: str) -> None:
    with pytest.raises(ValueError, match=SAFE_SCOPE_ERROR):
        validate_memory_scope(scope)
    with pytest.raises(ValueError, match=SAFE_SCOPE_ERROR):
        derive_memory_user_id("owner-1", scope)


@pytest.mark.parametrize("owner", ["", "   ", "a" * 257, "line\nbreak"])
def test_invalid_owner_fails_closed(owner: str) -> None:
    with pytest.raises(ValueError, match=SAFE_OWNER_ERROR):
        validate_owner_id(owner)
    with pytest.raises(ValueError, match=SAFE_OWNER_ERROR):
        derive_memory_user_id(owner, "default")
