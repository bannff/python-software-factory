"""Trivial in-tree reference ``PublishProvider`` — proves the port shape.

Publishes into the SAME storage this brick already owns (a mirrored,
read-only "published" projection of the artifact's content), addressed by
slug. This is the port's own self-test, not a real external destination —
real providers (GitHub, Notion, ...) are separate connector packs.
"""
from __future__ import annotations

from ..models import ArtifactRecord
from ..publish import PublishProviderError


class LocalPublishProvider:
    """Reference adapter: "publishing" = recording the current content hash."""

    provider_id = "local"

    def __init__(self) -> None:
        self._published: dict[str, str] = {}

    async def publish(self, artifact: ArtifactRecord) -> tuple[str, str]:
        external_ref = f"local:{artifact.tenant_id}:{artifact.owner_id}:{artifact.slug}"
        self._published[external_ref] = artifact.content_sha256
        return external_ref, f"published at content {artifact.content_sha256[:12]}"

    async def refresh(self, external_ref: str) -> tuple[str, str]:
        digest = self._published.get(external_ref)
        if digest is None:
            raise PublishProviderError("local_publication_not_found")
        return "published", f"still published at content {digest[:12]}"


__all__ = ["LocalPublishProvider"]
