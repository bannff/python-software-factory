"""DomainRuntime — wires a ManifestStore + EngagementStore
(bd:python-factory-w7i8k).

Business logic only — no MCP, no transport. ``get_manifest`` delegates to
the unified read path's total fallback (NEVER raises). Engagements are the
WORKSPACE axis: ``open_engagement`` pins active domain + manifest +
default-persona and returns all three in ONE call (no second round-trip).

N1 (strands-expert 69ad7193): the engagement pin / manifest MUST NOT enter
the Agent session key ``f"{agent_id}-{thread_id}"``. This runtime does not
touch agent session/cache logic at all — presentation is render-side only.

N2: persona stays manifest-agnostic. The only manifest→persona link is
``manifest.default_persona_id`` (soft, dangling-allowed). We resolve-or-
skip: explicit ``persona_id`` → ``manifest.default_persona_id`` → None. We
NEVER import the agent brick to validate the id; a dangling ref returns
None and the caller defaults (companion-x-default resolved elsewhere).
"""
from __future__ import annotations

import secrets
from typing import Any

from ..registry.unified import (
    get_manifest as _unified_get_manifest,
    set_default_store,
    unified_manifests,
)
from .adapters.memory import InMemoryEngagementStore, InMemoryManifestStore
from .models import Engagement, PresentationManifest
from .ports import EngagementStore, ManifestStore


class DomainRuntime:
    """Manifest + engagement runtime with default in-memory adapters."""

    def __init__(
        self,
        manifest_store: ManifestStore | None = None,
        engagement_store: EngagementStore | None = None,
    ) -> None:
        self.manifest_store: ManifestStore = (
            manifest_store or InMemoryManifestStore()
        )
        self.engagement_store: EngagementStore = (
            engagement_store or InMemoryEngagementStore()
        )
        # Wire the process-wide unified read path to THIS store so
        # unified_manifests()/get_manifest() overlay user manifests.
        set_default_store(self.manifest_store)

    # ── manifests (read) ─────────────────────────────────────────
    def get_manifest(self, domain_id: str) -> PresentationManifest:
        """Total lookup — unknown domain returns ``GENERIC_MANIFEST``."""
        return _unified_get_manifest(domain_id)

    def list_manifests(self) -> list[PresentationManifest]:
        """Built-ins + user manifests (single unified read path)."""
        return unified_manifests()

    # ── manifests (authoring) ────────────────────────────────────
    def create_manifest(
        self, manifest: PresentationManifest,
    ) -> PresentationManifest:
        """Persist a user manifest (DATA tier)."""
        self.manifest_store.save_manifest(manifest)
        return manifest

    def delete_manifest(self, domain_id: str) -> bool:
        """Remove a user manifest. Returns True if one was removed."""
        return self.manifest_store.delete_manifest(domain_id)

    # ── engagements (WORKSPACE axis) ─────────────────────────────
    def open_engagement(
        self, domain_id: str, persona_id: str | None = None,
    ) -> dict[str, Any]:
        """Pin active domain + manifest + default-persona in ONE call.

        Persona resolution order (resolve-or-skip, N2): explicit
        ``persona_id`` → ``manifest.default_persona_id`` → None. We NEVER
        import the agent brick; a None result lets the caller default to
        the backend persona (companion-x-default) elsewhere.
        """
        manifest = self.get_manifest(domain_id)
        resolved = persona_id or manifest.default_persona_id
        engagement = Engagement(
            id=secrets.token_hex(4),
            domain_id=domain_id,
            persona_id=resolved,
        )
        self.engagement_store.set_active(engagement)
        return {
            "engagement": engagement,
            "manifest": manifest,
            "persona_id": resolved,
        }

    def get_active_engagement(self) -> Engagement | None:
        """Return the active engagement, or None (GENERIC default)."""
        return self.engagement_store.get_active()

    def close_engagement(self) -> None:
        """Clear the active engagement → GENERIC_MANIFEST + persona None."""
        self.engagement_store.clear_active()
