"""Artifact update, immutable history, and tombstone SQL operations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable

from factory.storage.interface import SQLStore

from ..models import (
    ActorKind, ArtifactKind, ArtifactMutationEventType, ArtifactRecord,
    ArtifactVersion,
)
from .sql_rows import artifact_from, version_from


def update_artifact(
    sql: SQLStore, get: Callable[..., ArtifactRecord | None],
    tenant_id: str, owner_id: str, slug: str, expected_revision: int, *,
    actor_kind: ActorKind, event_type: ArtifactMutationEventType, name: str | None,
    description: str | None, kind: ArtifactKind | None,
    tags: tuple[str, ...] | None, content: str | None,
    content_sha256: str | None,
) -> ArtifactRecord | None:
    snapshot = 1 if content is not None or kind is not None else 0
    now = datetime.now(timezone.utc).isoformat()
    result = sql.execute(
        "UPDATE companion_artifacts SET name=COALESCE(:name,name), "
        "description=COALESCE(:description,description), kind=COALESCE(:kind,kind), "
        "tags=COALESCE(:tags,tags), content=COALESCE(:content,content), "
        "content_sha256=COALESCE(:content_sha256,content_sha256), "
        "version=version+:snapshot, revision=revision+1, actor_kind=:actor_kind, "
        "event_type=:event_type, updated_at=:now WHERE tenant_id=:tenant_id "
        "AND owner_id=:owner_id AND slug=:slug AND deleted_at IS NULL "
        "AND revision=:expected_revision",
        {"tenant_id": tenant_id, "owner_id": owner_id, "slug": slug,
         "expected_revision": expected_revision, "name": name,
         "description": description, "kind": kind.value if kind else None,
         "tags": json.dumps(tags, separators=(",", ":")) if tags is not None else None,
         "content": content, "content_sha256": content_sha256,
         "snapshot": snapshot, "actor_kind": actor_kind,
         "event_type": event_type, "now": now},
    )
    return get(tenant_id, owner_id, slug) if result.row_count == 1 else None


def list_versions(
    sql: SQLStore, tenant_id: str, owner_id: str, slug: str,
) -> list[ArtifactVersion]:
    rows = sql.fetch_all(
        "SELECT v.* FROM artifact_versions v JOIN companion_artifacts a ON "
        "a.tenant_id=v.tenant_id AND a.owner_id=v.owner_id AND a.slug=v.slug "
        "WHERE v.tenant_id=:tenant_id AND v.owner_id=:owner_id AND v.slug=:slug "
        "AND a.deleted_at IS NULL ORDER BY v.version DESC",
        {"tenant_id": tenant_id, "owner_id": owner_id, "slug": slug},
    )
    return [item for row in rows if (item := version_from(row)) is not None]


def tombstone_artifact(
    sql: SQLStore, tenant_id: str, owner_id: str, slug: str,
    expected_revision: int,
) -> bool:
    result = sql.execute(
        "UPDATE companion_artifacts SET deleted_at=:now,updated_at=:now,"
        "revision=revision+1,event_type='deleted' WHERE tenant_id=:tenant_id "
        "AND owner_id=:owner_id AND slug=:slug AND deleted_at IS NULL "
        "AND revision=:expected_revision",
        {"tenant_id": tenant_id, "owner_id": owner_id, "slug": slug,
         "expected_revision": expected_revision,
         "now": datetime.now(timezone.utc).isoformat()},
    )
    return result.row_count == 1


__all__ = ["list_versions", "tombstone_artifact", "update_artifact"]
