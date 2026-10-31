"""Artifact publication lifecycle (feature-map row 67).

Orchestrates publish/refresh against a ``PublishProviderRegistry`` and
persists the resulting ``PublicationNotice`` through the same store the
artifact itself lives in — the port decides WHAT happens externally, this
class decides WHEN and records the outcome truthfully (never invents a
"published" status the provider did not actually return).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import PublicationNotice
from .ports import ArtifactConflictError, ArtifactStore
from .publish import PublishProviderError, PublishProviderRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublishLifecycle:
    def __init__(self, store: ArtifactStore, registry: PublishProviderRegistry) -> None:
        self.store = store
        self.registry = registry

    async def publish(self, tenant: str, owner: str, slug: str,
                       provider_id: str) -> PublicationNotice:
        artifact = self.store.get(tenant, owner, slug)
        if artifact is None:
            raise ValueError("artifact_not_found")
        try:
            provider = self.registry.get(provider_id)
            external_ref, detail = await provider.publish(artifact)
        except PublishProviderError as exc:
            raise ValueError(f"publish_failed:{exc}") from exc
        notice = self.store.upsert_publication(
            tenant, owner, slug, provider_id, external_ref, detail, _now(),
        )
        if notice is None:
            raise ArtifactConflictError("publication write failed")
        return notice

    async def refresh(self, tenant: str, owner: str, slug: str,
                       provider_id: str) -> PublicationNotice:
        current = self.store.get_publication(tenant, owner, slug, provider_id)
        if current is None:
            raise ValueError("publication_not_found")
        try:
            provider = self.registry.get(provider_id)
        except PublishProviderError as exc:
            raise ValueError(f"unknown_publish_provider:{exc}") from exc
        try:
            status, detail = await provider.refresh(current.external_ref)
        except PublishProviderError as exc:
            status, detail = "unavailable", f"refresh_failed:{exc}"
        updated = self.store.update_publication_status(
            tenant, owner, slug, provider_id, status, detail, _now(),
        )
        if updated is None:
            raise ValueError("publication_not_found")
        return updated

    def get(self, tenant: str, owner: str, slug: str,
            provider_id: str) -> PublicationNotice:
        notice = self.store.get_publication(tenant, owner, slug, provider_id)
        if notice is None:
            raise ValueError("publication_not_found")
        return notice

    def unpublish(self, tenant: str, owner: str, slug: str,
                  provider_id: str) -> None:
        if not self.store.remove_publication(tenant, owner, slug, provider_id):
            raise ValueError("publication_not_found")


__all__ = ["PublishLifecycle"]
