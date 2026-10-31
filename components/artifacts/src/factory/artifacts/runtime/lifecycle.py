"""Artifacts save and read lifecycle."""
from __future__ import annotations

import hashlib
import json

from .models import (
    ActorKind, ArtifactKind, ArtifactMutationEventType, ArtifactRecord,
    ArtifactVersion, ArtifactWriteResult, validate_content,
)
from .ports import ArtifactConflictError, ArtifactStore


class ArtifactLifecycle:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def save(
        self, tenant_id: str, owner_id: str, name: str, content: str, *,
        description: str = "", kind: ArtifactKind = ArtifactKind.MARKDOWN,
        tags: tuple[str, ...] = (), actor_kind: ActorKind = "agent",
        idempotency_key: str | None = None,
    ) -> ArtifactWriteResult:
        # Validate content/name/tags before persistence through the strict record model.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        content = validate_content(content)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ArtifactRecord(
            tenant_id=tenant_id, owner_id=owner_id, slug="validation",
            name=name, description=description, kind=kind, tags=tags,
            content=content, content_sha256=digest, created_at=now, updated_at=now,
        )
        material = json.dumps({
            "name": name.strip(), "description": description,
            "kind": kind.value, "tags": tags, "content_sha256": digest,
        }, sort_keys=True, separators=(",", ":")).encode()
        request = hashlib.sha256(material).hexdigest()
        return self.store.save(
            tenant_id, owner_id, name.strip(), content, description=description,
            kind=kind, tags=tags, actor_kind=actor_kind,
            idempotency_key=idempotency_key, request_sha256=request,
            content_sha256=digest,
        )

    def get(self, tenant_id: str, owner_id: str, slug: str) -> ArtifactRecord:
        artifact = self.store.get(tenant_id, owner_id, slug)
        if artifact is None:
            raise ValueError("artifact_not_found")
        return artifact

    def list(self, tenant_id: str, owner_id: str, *, limit: int = 100,
             offset: int = 0, name: str | None = None,
             kind: ArtifactKind | None = None,
             tag: str | None = None) -> list[ArtifactRecord]:
        return self.store.list(
            tenant_id, owner_id, limit=limit, offset=offset,
            name=name, kind=kind, tag=tag,
        )
    def update(
        self, tenant_id: str, owner_id: str, slug: str,
        expected_revision: int, *, actor_kind: ActorKind,
        name: str | None = None, description: str | None = None,
        kind: ArtifactKind | None = None, tags: tuple[str, ...] | None = None,
        content: str | None = None, event_type: ArtifactMutationEventType = "updated",
    ) -> ArtifactWriteResult:
        current = self.get(tenant_id, owner_id, slug)
        candidate_content = validate_content(content) if content is not None else current.content
        digest = hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
        from datetime import datetime, timezone
        ArtifactRecord(
            tenant_id=tenant_id, owner_id=owner_id, slug=slug,
            name=name if name is not None else current.name,
            description=description if description is not None else current.description,
            kind=kind if kind is not None else current.kind,
            tags=tags if tags is not None else current.tags,
            content=candidate_content, content_sha256=digest,
            version=current.version + (1 if content is not None or kind is not None else 0),
            revision=current.revision + 1, created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        updated = self.store.update(
            tenant_id, owner_id, slug, expected_revision,
            actor_kind=actor_kind, event_type=event_type, name=name,
            description=description, kind=kind, tags=tags, content=content,
            content_sha256=digest if content is not None else None,
        )
        if updated is None:
            raise ArtifactConflictError("artifact revision conflict")
        outcome = "reverted" if event_type == "reverted" else "updated"
        return ArtifactWriteResult(outcome=outcome, artifact=updated)

    def versions(self, tenant_id: str, owner_id: str,
                 slug: str) -> list[ArtifactVersion]:
        self.get(tenant_id, owner_id, slug)
        return self.store.list_versions(tenant_id, owner_id, slug)

    def revert(self, tenant_id: str, owner_id: str, slug: str,
               version: int, expected_revision: int,
               actor_kind: ActorKind) -> ArtifactWriteResult:
        self.get(tenant_id, owner_id, slug)
        target = self.store.get_version(tenant_id, owner_id, slug, version)
        if target is None:
            raise ValueError("artifact_version_not_found")
        return self.update(
            tenant_id, owner_id, slug, expected_revision,
            actor_kind=actor_kind, kind=target.kind, content=target.content,
            event_type="reverted",
        )

    def tombstone(self, tenant_id: str, owner_id: str, slug: str,
                  expected_revision: int) -> ArtifactRecord:
        current = self.get(tenant_id, owner_id, slug)
        if not self.store.tombstone(
            tenant_id, owner_id, slug, expected_revision,
        ):
            raise ArtifactConflictError("artifact revision conflict")
        return current.model_copy(update={"revision": current.revision + 1})

    def purge(self, tenant_id: str, owner_id: str, slug: str,
              expected_revision: int, actor_kind: ActorKind) -> None:
        if actor_kind != "human":
            raise PermissionError("artifact human actor required")
        if self.store.get_tombstone(tenant_id, owner_id, slug) is None:
            raise ValueError("artifact_not_found")
        from uuid import uuid4
        if not self.store.purge_artifact(
            tenant_id, owner_id, slug, expected_revision, uuid4().hex,
        ):
            raise ArtifactConflictError("artifact revision conflict")


__all__ = ["ArtifactLifecycle"]
