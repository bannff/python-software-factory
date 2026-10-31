"""DomainRuntime + store-seam tests (bd:python-factory-w7i8k).

Behaviour verified:
  * Engagement lifecycle: ``open_engagement`` pins + returns
    {engagement, manifest, persona_id}; persona resolution order
    (explicit -> manifest.default_persona_id -> None); ``get_active_engagement``
    reflects it; ``close_engagement`` clears it.
  * Store seam hygiene: ``set_default_store`` / ``reset_default_store``;
    after set, ``unified_manifests()`` overlays the user store; after reset,
    built-ins only.

TEST-HYGIENE GOTCHA: ``DomainRuntime.__init__`` calls
``set_default_store`` (process-wide). The autouse fixture below calls
``reset_default_store()`` before AND after every test so a runtime built in
one test cannot leak its store into the next.
"""
from __future__ import annotations

import pytest

from factory.domain.registry import unified
from factory.domain.runtime.adapters.memory import InMemoryManifestStore
from factory.domain.runtime.models import (
    GENERIC_MANIFEST,
    Engagement,
    PresentationManifest,
)
from factory.domain.runtime.runtime import DomainRuntime


@pytest.fixture(autouse=True)
def _reset_store():
    """Isolate the process-wide default store around every test."""
    unified.reset_default_store()
    yield
    unified.reset_default_store()


def test_open_engagement_returns_triplet() -> None:
    rt = DomainRuntime()
    result = rt.open_engagement("security")

    assert set(result) == {"engagement", "manifest", "persona_id"}
    assert isinstance(result["engagement"], Engagement)
    assert isinstance(result["manifest"], PresentationManifest)
    assert result["engagement"].domain_id == "security"
    assert result["manifest"].domain_id == "security"


def test_persona_resolution_explicit_wins() -> None:
    """Explicit persona_id beats the manifest default."""
    rt = DomainRuntime()
    result = rt.open_engagement("security", persona_id="custom-persona")
    assert result["persona_id"] == "custom-persona"
    assert result["engagement"].persona_id == "custom-persona"


def test_persona_resolution_falls_back_to_manifest_default() -> None:
    """No explicit persona -> manifest.default_persona_id (security-analyst)."""
    rt = DomainRuntime()
    result = rt.open_engagement("security")
    assert result["persona_id"] == "security-analyst"


def test_persona_resolution_none_for_generic() -> None:
    """Unknown/generic domain has no default persona -> None."""
    rt = DomainRuntime()
    result = rt.open_engagement("totally-unknown")
    assert result["persona_id"] is None
    # Unknown domain still resolves a manifest (the generic baseline).
    assert result["manifest"] is GENERIC_MANIFEST


def test_get_active_reflects_open_then_close() -> None:
    rt = DomainRuntime()
    assert rt.get_active_engagement() is None

    rt.open_engagement("security")
    active = rt.get_active_engagement()
    assert active is not None
    assert active.domain_id == "security"

    rt.close_engagement()
    assert rt.get_active_engagement() is None


def test_get_manifest_total_via_runtime() -> None:
    """Runtime.get_manifest delegates to the total fallback."""
    rt = DomainRuntime()
    assert rt.get_manifest("nope-not-here") is GENERIC_MANIFEST


def test_store_seam_overlays_user_manifest() -> None:
    """After set_default_store, unified_manifests overlays user manifests."""
    store = InMemoryManifestStore()
    store.save_manifest(PresentationManifest(domain_id="finance"))
    unified.set_default_store(store)

    ids = {m.domain_id for m in unified.unified_manifests()}
    assert "finance" in ids
    assert unified.get_manifest("finance").domain_id == "finance"


def test_store_seam_reset_returns_builtins_only() -> None:
    """After reset, the overlay is gone — built-ins only."""
    store = InMemoryManifestStore()
    store.save_manifest(PresentationManifest(domain_id="finance"))
    unified.set_default_store(store)
    assert "finance" in {m.domain_id for m in unified.unified_manifests()}

    unified.reset_default_store()
    ids = {m.domain_id for m in unified.unified_manifests()}
    assert "finance" not in ids
    assert unified.get_manifest("finance") is GENERIC_MANIFEST


def test_runtime_wires_its_own_store() -> None:
    """DomainRuntime.__init__ wires its manifest store into the read path."""
    rt = DomainRuntime()
    rt.create_manifest(PresentationManifest(domain_id="finance"))
    # The free-function read path now sees the runtime's user manifest.
    assert "finance" in {m.domain_id for m in unified.unified_manifests()}


def test_create_then_delete_manifest() -> None:
    rt = DomainRuntime()
    rt.create_manifest(PresentationManifest(domain_id="finance"))
    assert rt.delete_manifest("finance") is True
    # Idempotent: second delete returns False.
    assert rt.delete_manifest("finance") is False
