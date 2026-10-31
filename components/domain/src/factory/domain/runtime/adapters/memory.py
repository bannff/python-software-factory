"""In-memory adapters for the domain brick (v1 LOCAL, bd:python-factory-w7i8k).

The only adapters v1 ships. The Protocol ports (``runtime/ports.py``) ARE
the seam for a future disk/AgentCore backend — no speculative adapters
here (mirrors how the persona registry defaults its process-wide store to
``None`` = built-ins only).
"""
from __future__ import annotations

from ..models import Engagement, PresentationManifest


class InMemoryManifestStore:
    """In-memory ``ManifestStore`` — user manifests keyed by domain_id."""

    def __init__(self) -> None:
        self._manifests: dict[str, PresentationManifest] = {}

    def load_manifests(self) -> list[PresentationManifest]:
        return list(self._manifests.values())

    def save_manifest(self, manifest: PresentationManifest) -> None:
        self._manifests[manifest.domain_id] = manifest

    def delete_manifest(self, domain_id: str) -> bool:
        return self._manifests.pop(domain_id, None) is not None


class InMemoryEngagementStore:
    """In-memory ``EngagementStore`` — a single active engagement slot."""

    def __init__(self) -> None:
        self._active: Engagement | None = None

    def get_active(self) -> Engagement | None:
        return self._active

    def set_active(self, engagement: Engagement) -> None:
        self._active = engagement

    def clear_active(self) -> None:
        self._active = None
