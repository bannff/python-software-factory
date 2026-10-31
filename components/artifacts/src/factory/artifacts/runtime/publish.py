"""Provider-neutral publish port (feature-map row 67).

Real external providers (GitHub, Notion, ...) are connector packs that
implement this port later without touching callers — the port + a trivial
in-tree reference adapter (``LocalPublishProvider``) proves the shape end to
end now. No provider token ever crosses this boundary by value; a real
adapter must resolve its credential by env-var NAME (the ``owner_secrets``
pattern), never accept one as an argument here.
"""
from __future__ import annotations

from typing import Protocol

from .models import ArtifactRecord


class PublishProviderError(RuntimeError):
    """A publish or refresh attempt the provider itself rejected or lost."""


class PublishProvider(Protocol):
    """One publish target. Registered by name; callers never see its token."""

    @property
    def provider_id(self) -> str: ...

    async def publish(
        self, artifact: ArtifactRecord,
    ) -> tuple[str, str]:
        """Push ``artifact`` out; return (external_ref, detail)."""
        ...

    async def refresh(self, external_ref: str) -> tuple[str, str]:
        """Re-check a prior publish; return (status, detail)."""
        ...


class PublishProviderRegistry:
    """Name -> ``PublishProvider`` lookup; owner-editable config chooses the name."""

    def __init__(self, providers: dict[str, PublishProvider]) -> None:
        self._providers = dict(providers)

    def get(self, provider_id: str) -> PublishProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise PublishProviderError(f"unknown_publish_provider:{provider_id}")
        return provider

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


__all__ = [
    "PublishProvider", "PublishProviderError", "PublishProviderRegistry",
]
