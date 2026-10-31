"""Built-in presentation manifests — the CODE seed (bd:python-factory-w7i8k).

``MANIFESTS_TYPED`` is the immutable built-in seed list, the analog of the
agent brick's ``AGENTS_TYPED``. Built-ins stay CODE; user-authored
manifests are DATA behind a ``ManifestStore`` (``runtime/ports.py``).
GENERIC is always first (the byte-identical baseline); SECURITY is pack
#1, split into its own ``defaults_security`` module to mirror the agent
brick's per-domain defaults split.
"""
from __future__ import annotations

from ..runtime.models import GENERIC_MANIFEST, PresentationManifest
from .defaults_security import SECURITY_MANIFEST

MANIFESTS_TYPED: list[PresentationManifest] = [GENERIC_MANIFEST, SECURITY_MANIFEST]

__all__ = ["MANIFESTS_TYPED"]
