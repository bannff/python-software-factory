"""Hypothesis + unit tests for the domain unified read path
(bd:python-factory-w7i8k).

Properties verified:
  * TOTALITY CANARY (#1): ``get_manifest(s)`` for ANY fuzzed string never
    raises, never returns None, always returns a ``PresentationManifest``;
    any ``domain_id`` NOT in the built-in/store set returns the SAME
    ``GENERIC_MANIFEST`` object (asserted by identity ``is``).
  * ``merge_manifests``: built-ins WIN on domain_id collision, GENERIC is
    always present, built-in order is preserved, user-only manifests append.

These exercise public behaviour only (no ``_private`` access).
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.domain.registry import unified
from factory.domain.registry.manifests import MANIFESTS_TYPED
from factory.domain.runtime.models import GENERIC_MANIFEST, PresentationManifest

# The built-in domain_ids resolvable with NO user store wired.
_BUILTIN_IDS = {m.domain_id for m in MANIFESTS_TYPED}


@settings(max_examples=200)
@given(s=st.text())
def test_get_manifest_is_total(s: str) -> None:
    """ANY string -> a PresentationManifest, never raising, never None.

    Empty, unicode, very long, charset-invalid, and whitespace strings are
    all covered by ``st.text()``. Unknown ids collapse onto the single
    ``GENERIC_MANIFEST`` baseline (identity check).
    """
    # Built-ins-only resolution (no process-wide user store).
    unified.reset_default_store()
    result = unified.get_manifest(s)

    assert result is not None
    assert isinstance(result, PresentationManifest)
    if s not in _BUILTIN_IDS:
        assert result is GENERIC_MANIFEST


@settings(max_examples=100)
@given(s=st.text(min_size=1, max_size=300))
def test_get_manifest_never_raises_on_nonempty(s: str) -> None:
    """A second fuzz focused on long/charset-invalid ids — totality holds."""
    unified.reset_default_store()
    # Must not raise for any input.
    assert isinstance(unified.get_manifest(s), PresentationManifest)


def test_generic_is_in_builtins() -> None:
    """GENERIC_MANIFEST is always part of the built-in seed."""
    assert GENERIC_MANIFEST in MANIFESTS_TYPED
    assert "generic" in _BUILTIN_IDS


def test_merge_builtin_wins_on_collision() -> None:
    """A user manifest shadowing a built-in domain_id is dropped."""
    builtins = list(MANIFESTS_TYPED)
    shadow = PresentationManifest(domain_id="security", display_name="HIJACK")
    merged = unified.merge_manifests(builtins, [shadow])

    by_id = {m.domain_id: m for m in merged}
    # Built-in security wins; the user "HIJACK" display_name never appears.
    assert by_id["security"].display_name != "HIJACK"
    assert by_id["security"] in builtins


def test_merge_generic_always_present() -> None:
    """GENERIC survives any merge."""
    merged = unified.merge_manifests(list(MANIFESTS_TYPED), [])
    assert any(m is GENERIC_MANIFEST for m in merged)


def test_merge_builtin_order_preserved() -> None:
    """Built-in ordering is preserved at the front of the merged list."""
    builtins = list(MANIFESTS_TYPED)
    merged = unified.merge_manifests(builtins, [])
    head = [m.domain_id for m in merged][: len(builtins)]
    assert head == [m.domain_id for m in builtins]


def test_merge_user_only_manifest_appends() -> None:
    """A user-only domain_id appends after the built-ins."""
    builtins = list(MANIFESTS_TYPED)
    extra = PresentationManifest(domain_id="finance", display_name="Finance")
    merged = unified.merge_manifests(builtins, [extra])

    ids = [m.domain_id for m in merged]
    assert "finance" in ids
    assert ids.index("finance") >= len(builtins)
    # And it resolves as itself, not GENERIC.
    by_id = {m.domain_id: m for m in merged}
    assert by_id["finance"].display_name == "Finance"


def test_merge_empty_inputs() -> None:
    """Edge case: both inputs empty -> empty merge (no crash)."""
    assert unified.merge_manifests([], []) == []
