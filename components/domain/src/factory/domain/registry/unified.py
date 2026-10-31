"""Unified manifest registry — ONE read path for domain presentation
manifests (bd:python-factory-w7i8k, meta-architect verdict c2d04276).

The manifest/engagement analog of the agent brick's
``registry/unified.py`` persona registry. Built-ins stay CODE
(``MANIFESTS_TYPED`` is the immutable seed); user-created manifests are
DATA behind a ``ManifestStore`` (``runtime/ports.py``). ``merge_manifests``
seeds built-ins FIRST then overlays the store, with built-ins WINNING on
``domain_id`` collision (a user may not shadow a built-in id).
``unified_manifests`` is the single read path.

Default-store seam: ``set_default_store`` wires a process-wide store so
the free-function read path sees the same user manifests the runtime
does. Default is ``None`` → only built-ins resolve → ``GENERIC_MANIFEST``
is byte-identical whether or not any store exists (copy of unified.py
verbatim).

KEY DIVERGENCE from personas: ``get_manifest`` NEVER raises and NEVER
returns None — an unknown domain returns ``GENERIC_MANIFEST``. This total
generic fallback IS the branch-free guarantee (no caller ever has to
None-check or try/except a domain lookup).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..runtime.models import GENERIC_MANIFEST, PresentationManifest

if TYPE_CHECKING:
    from ..runtime.ports import ManifestStore

logger = logging.getLogger(__name__)

__all__ = [
    "merge_manifests",
    "unified_manifests",
    "get_manifest",
    "set_default_store",
    "get_default_store",
    "reset_default_store",
]

# Process-wide store for user-created manifests. ``None`` = built-ins only
# (byte-identical default). Composition roots set this to the live store
# so the free-function read path + the runtime agree.
_default_store: "ManifestStore | None" = None


def merge_manifests(
    builtins: list[PresentationManifest],
    store_manifests: list[PresentationManifest],
) -> list[PresentationManifest]:
    """Seed ``builtins`` FIRST, then overlay ``store_manifests``.

    Built-ins WIN on domain_id collision — a user manifest whose
    domain_id shadows a built-in is rejected (logged + skipped), never the
    other way round. Built-in order is preserved; user-only manifests
    append after.
    """
    merged: dict[str, PresentationManifest] = {}
    builtin_ids = {b.domain_id for b in builtins}
    for m in builtins:
        merged[m.domain_id] = m
    for m in store_manifests:
        if m.domain_id in builtin_ids:
            logger.warning(
                "user manifest %r shadows a built-in domain_id; built-in "
                "wins (user manifest ignored)", m.domain_id,
            )
            continue
        merged[m.domain_id] = m
    return list(merged.values())


def unified_manifests() -> list[PresentationManifest]:
    """The single manifest read path: built-ins + the default store.

    Reads ``MANIFESTS_TYPED`` live so in-process registrations (tests,
    bootstrap) are visible, and overlays the process-wide store.
    """
    from .manifests import MANIFESTS_TYPED
    store = _default_store
    store_manifests = store.load_manifests() if store is not None else []
    return merge_manifests(list(MANIFESTS_TYPED), store_manifests)


def get_manifest(domain_id: str) -> PresentationManifest:
    """Total lookup — NEVER raises, NEVER returns None.

    Unknown domain → ``GENERIC_MANIFEST``. This is the branch-free
    guarantee: callers never None-check a domain lookup.
    """
    for m in unified_manifests():
        if m.domain_id == domain_id:
            return m
    return GENERIC_MANIFEST


def set_default_store(store: "ManifestStore | None") -> None:
    """Wire the process-wide user-manifest store (seam for AgentCore)."""
    global _default_store
    _default_store = store


def get_default_store() -> "ManifestStore | None":
    """Return the process-wide user-manifest store (``None`` if unset)."""
    return _default_store


def reset_default_store() -> None:
    """Clear the process-wide store (test hygiene → built-ins only)."""
    global _default_store
    _default_store = None
