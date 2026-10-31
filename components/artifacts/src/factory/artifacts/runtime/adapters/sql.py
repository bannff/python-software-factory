"""Artifacts adapter over Storage's public SQLStore."""
from __future__ import annotations

import json
from typing import Any

from factory.storage.interface import SQLStore

from ..models import ActorKind, ArtifactKind, ArtifactWriteResult
from ..ports import ArtifactConflictError, ArtifactSlugExhaustedError
from ..slug import slug_candidate, slugify
from .sql_authoring import AuthoringSQLMixin, init_purge
from .sql_comments import CommentSQLMixin, init_comments
from .sql_folders import FolderSQLMixin, init_folders
from .sql_publications import PublicationSQLMixin, init_publications
from .sql_rows import (
    ARTIFACT_SCHEMA, DELETE_GUARD_TRIGGER, IDEMPOTENCY_INDEX,
    IMMUTABLE_TRIGGER, VERSION_SCHEMA, VERSION_UPDATE_TRIGGER,
    V1_TRIGGER, artifact_from, version_from,
)


class SQLArtifactStore(
    FolderSQLMixin, CommentSQLMixin, AuthoringSQLMixin, PublicationSQLMixin,
):
    """Single-statement owner-scoped artifact persistence."""

    def __init__(self, sql: SQLStore) -> None:
        self._sql = sql
        for statement in (
            ARTIFACT_SCHEMA, IDEMPOTENCY_INDEX, VERSION_SCHEMA,
            V1_TRIGGER, IMMUTABLE_TRIGGER, DELETE_GUARD_TRIGGER,
            VERSION_UPDATE_TRIGGER,
        ):
            sql.execute(statement)
        columns = {row["name"] for row in sql.fetch_all(
            "PRAGMA table_info(companion_artifacts)",
        )}
        migrations = {
            "folder_id": "ALTER TABLE companion_artifacts ADD COLUMN folder_id TEXT",
            "purge_token": "ALTER TABLE companion_artifacts ADD COLUMN purge_token TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                sql.execute(statement)
        init_folders(sql)
        init_comments(sql)
        comment_columns = {row["name"] for row in sql.fetch_all(
            "PRAGMA table_info(artifact_comments)",
        )}
        if "anchor_text" not in comment_columns:
            sql.execute("ALTER TABLE artifact_comments ADD COLUMN anchor_text TEXT")
        init_purge(sql)
        init_publications(sql)

    def save(
        self, tenant_id: str, owner_id: str, name: str, content: str, *,
        description: str, kind: ArtifactKind, tags: tuple[str, ...],
        actor_kind: ActorKind, idempotency_key: str | None,
        request_sha256: str, content_sha256: str,
    ) -> ArtifactWriteResult:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        common = {
            "tenant_id": tenant_id, "owner_id": owner_id, "name": name,
            "description": description, "kind": kind.value,
            "tags": json.dumps(tags, separators=(",", ":")),
            "content": content, "content_sha256": content_sha256,
            "idempotency_key": idempotency_key,
            "request_sha256": request_sha256 if idempotency_key else None,
            "actor_kind": actor_kind, "now": now,
        }
        base = slugify(name)
        for attempt in range(1, 65):
            slug = slug_candidate(base, attempt)
            result = self._sql.execute(
                "INSERT INTO companion_artifacts (tenant_id,owner_id,slug,name,"
                "description,kind,tags,content,content_sha256,idempotency_key,"
                "request_sha256,version,revision,actor_kind,event_type,created_at,updated_at) "
                "VALUES (:tenant_id,:owner_id,:slug,:name,:description,:kind,"
                ":tags,:content,:content_sha256,:idempotency_key,:request_sha256,"
                "1,1,:actor_kind,'created',:now,:now) ON CONFLICT DO NOTHING",
                {**common, "slug": slug},
            )
            if result.row_count == 1:
                artifact = self.get(tenant_id, owner_id, slug)
                if artifact is None:
                    raise RuntimeError("artifact creation unavailable")
                return ArtifactWriteResult(outcome="created", artifact=artifact)
            replay = self._by_idempotency(tenant_id, owner_id, idempotency_key)
            if replay is not None:
                if replay["request_sha256"] != request_sha256:
                    raise ArtifactConflictError("artifact idempotency conflict")
                artifact = artifact_from(replay)
                if artifact is None:
                    raise RuntimeError("artifact replay unavailable")
                return ArtifactWriteResult(outcome="matched", artifact=artifact)
        raise ArtifactSlugExhaustedError("artifact slug namespace exhausted")

    def get(self, tenant_id: str, owner_id: str, slug: str):
        return artifact_from(self._sql.fetch_one(
            "SELECT * FROM companion_artifacts WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND slug=:slug AND deleted_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "slug": slug},
        ))

    def list(self, tenant_id: str, owner_id: str, *, limit: int, offset: int,
             name: str | None, kind: ArtifactKind | None, tag: str | None):
        rows = self._sql.fetch_all(
            "SELECT * FROM companion_artifacts WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND deleted_at IS NULL "
            "AND (:name IS NULL OR lower(name) LIKE '%' || lower(:name) || '%') "
            "AND (:kind IS NULL OR kind=:kind) "
            "AND (:tag IS NULL OR EXISTS (SELECT 1 FROM json_each(tags) "
            "WHERE value=:tag)) ORDER BY updated_at DESC,slug "
            "LIMIT :limit OFFSET :offset",
            {"tenant_id": tenant_id, "owner_id": owner_id, "name": name,
             "kind": kind.value if kind else None, "tag": tag,
             "limit": limit, "offset": offset},
        )
        return [item for row in rows if (item := artifact_from(row)) is not None]

    def get_version(self, tenant_id: str, owner_id: str, slug: str, version: int):
        return version_from(self._sql.fetch_one(
            "SELECT v.* FROM artifact_versions v JOIN companion_artifacts a ON "
            "a.tenant_id=v.tenant_id AND a.owner_id=v.owner_id AND a.slug=v.slug "
            "WHERE v.tenant_id=:tenant_id AND v.owner_id=:owner_id "
            "AND v.slug=:slug AND v.version=:version AND a.deleted_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id,
             "slug": slug, "version": version},
        ))

    def update(self, tenant_id: str, owner_id: str, slug: str,
               expected_revision: int, **changes):
        from .sql_versions import update_artifact
        return update_artifact(
            self._sql, self.get, tenant_id, owner_id, slug,
            expected_revision, **changes,
        )

    def get_tombstone(self, tenant_id: str, owner_id: str, slug: str):
        return artifact_from(self._sql.fetch_one(
            "SELECT * FROM companion_artifacts WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND slug=:slug AND deleted_at IS NOT NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "slug": slug},
        ))

    def list_versions(self, tenant_id: str, owner_id: str, slug: str):
        from .sql_versions import list_versions
        return list_versions(self._sql, tenant_id, owner_id, slug)

    def tombstone(self, tenant_id: str, owner_id: str, slug: str,
                  expected_revision: int) -> bool:
        from .sql_versions import tombstone_artifact
        return tombstone_artifact(
            self._sql, tenant_id, owner_id, slug, expected_revision,
        )

    def _by_idempotency(self, tenant_id: str, owner_id: str,
                        key: str | None) -> dict[str, Any] | None:
        if key is None:
            return None
        return self._sql.fetch_one(
            "SELECT * FROM companion_artifacts WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND idempotency_key=:key",
            {"tenant_id": tenant_id, "owner_id": owner_id, "key": key},
        )


__all__ = ["SQLArtifactStore"]
