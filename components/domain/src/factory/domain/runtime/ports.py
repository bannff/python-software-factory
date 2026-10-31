"""Abstract ports for the domain brick — runtime Protocol interfaces
(bd:python-factory-w7i8k).

Mirrors the agent brick's ``RegistryStore`` pattern. Built-in manifests
stay in CODE (``registry/manifests.MANIFESTS_TYPED``); these ports own
only the DATA tier — manifests + engagements created at runtime. The
in-memory adapters back local dev (v1); an AgentCore/disk-backed adapter
slots in later behind the same Protocol (tenet #2 polymorphic). The
Protocol port IS the seam — there is intentionally NO disk or AgentCore
adapter in v1.
"""
from __future__ import annotations

from typing import Protocol

from .models import Engagement, PresentationManifest


class ManifestStore(Protocol):
    """Port: persistence for USER-created presentation manifests.

    DATA tier only — built-in manifests stay CODE. Mirrors the agent
    brick's ``RegistryStore`` exactly.
    """

    def load_manifests(self) -> list[PresentationManifest]:
        """Return all persisted user manifests (validated)."""
        ...

    def save_manifest(self, manifest: PresentationManifest) -> None:
        """Persist a single user manifest (create or update)."""
        ...

    def delete_manifest(self, domain_id: str) -> bool:
        """Remove a persisted manifest. Return True if one was removed."""
        ...


class EngagementStore(Protocol):
    """Port: the workspace-scoped active engagement (WORKSPACE axis).

    Exactly one engagement is active per workspace at a time. ``None``
    means no engagement is pinned (the ``GENERIC_MANIFEST`` + persona-None
    default — byte-identical to today).
    """

    def get_active(self) -> Engagement | None:
        """Return the active engagement, or None if none is pinned."""
        ...

    def set_active(self, engagement: Engagement) -> None:
        """Pin the active engagement (replaces any current one)."""
        ...

    def clear_active(self) -> None:
        """Clear the active engagement (back to the GENERIC default)."""
        ...
