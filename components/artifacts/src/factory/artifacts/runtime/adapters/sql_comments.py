"""Owner-scoped bounded artifact comment persistence."""
from __future__ import annotations

from factory.storage.interface import SQLStore

from .sql_rows import comment_from

COMMENT_SCHEMA = """CREATE TABLE IF NOT EXISTS artifact_comments (
 tenant_id TEXT NOT NULL,owner_id TEXT NOT NULL,id TEXT NOT NULL,slug TEXT NOT NULL,
 root_id TEXT NOT NULL,parent_id TEXT,body TEXT NOT NULL,actor_kind TEXT NOT NULL,
 status TEXT NOT NULL,revision INTEGER NOT NULL,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,deleted_at TEXT,anchor_text TEXT,
 PRIMARY KEY (tenant_id,owner_id,id))"""
COMMENT_DELETE_TRIGGER = """CREATE TRIGGER IF NOT EXISTS comment_root_delete
 AFTER UPDATE OF deleted_at ON artifact_comments WHEN OLD.parent_id IS NULL
 AND OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL BEGIN
 UPDATE artifact_comments SET deleted_at=NEW.deleted_at,revision=revision+1,
  updated_at=NEW.updated_at WHERE tenant_id=OLD.tenant_id
  AND owner_id=OLD.owner_id AND root_id=OLD.id AND parent_id IS NOT NULL
  AND deleted_at IS NULL; END"""


def init_comments(sql: SQLStore) -> None:
    sql.execute(COMMENT_SCHEMA)
    sql.execute(COMMENT_DELETE_TRIGGER)


class CommentSQLMixin:
    _sql: SQLStore

    def add_comment(self, tenant: str, owner: str, comment_id: str, slug: str,
                    parent_id: str | None, body: str, actor: str, now: str,
                    anchor_text: str | None = None):
        result = self._sql.execute(
            "INSERT OR IGNORE INTO artifact_comments SELECT :t,:o,:id,:slug,"
            "COALESCE(:parent,:id),:parent,:body,:actor,'open',1,:now,:now,NULL,"
            ":anchor "
            "FROM companion_artifacts a WHERE a.tenant_id=:t AND a.owner_id=:o "
            "AND a.slug=:slug AND a.deleted_at IS NULL AND (SELECT COUNT(*) FROM "
            "artifact_comments c WHERE c.tenant_id=:t AND c.owner_id=:o "
            "AND c.slug=:slug AND c.deleted_at IS NULL)<500 AND (:parent IS NULL "
            "OR EXISTS (SELECT 1 FROM artifact_comments p WHERE p.tenant_id=:t "
            "AND p.owner_id=:o AND p.slug=:slug AND p.id=:parent "
            "AND p.parent_id IS NULL AND p.deleted_at IS NULL))",
            {"t": tenant, "o": owner, "id": comment_id, "slug": slug,
             "parent": parent_id, "body": body, "actor": actor, "now": now,
             "anchor": anchor_text},
        )
        return self.get_comment(tenant, owner, slug, comment_id) if result.row_count else None

    def list_comments(self, tenant: str, owner: str, slug: str):
        return [comment_from(row) for row in self._sql.fetch_all(
            "SELECT c.* FROM artifact_comments c JOIN companion_artifacts a ON "
            "a.tenant_id=c.tenant_id AND a.owner_id=c.owner_id AND a.slug=c.slug "
            "WHERE c.tenant_id=:t AND c.owner_id=:o AND c.slug=:slug "
            "AND c.deleted_at IS NULL AND a.deleted_at IS NULL "
            "ORDER BY c.created_at,c.id",
            {"t": tenant, "o": owner, "slug": slug},
        )]

    def get_comment(self, tenant: str, owner: str, slug: str, comment_id: str):
        return next((c for c in self.list_comments(tenant, owner, slug)
                     if c.id == comment_id), None)

    def mark_comment_review(self, tenant: str, owner: str, slug: str,
                            comment_id: str, now: str):
        result = self._sql.execute(
            "UPDATE artifact_comments SET status='review',revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND slug=:slug "
            "AND id=:id AND parent_id IS NULL AND status='open' AND deleted_at IS NULL "
            "AND EXISTS (SELECT 1 FROM companion_artifacts WHERE tenant_id=:t "
            "AND owner_id=:o AND slug=:slug AND deleted_at IS NULL)",
            {"now": now, "t": tenant, "o": owner,
             "slug": slug, "id": comment_id},
        )
        return self.get_comment(tenant, owner, slug, comment_id) if result.row_count else None

    def resolve_comment(self, tenant: str, owner: str, slug: str,
                        comment_id: str, expected: int, now: str):
        result = self._sql.execute(
            "UPDATE artifact_comments SET status='resolved',revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND slug=:slug "
            "AND id=:id AND parent_id IS NULL AND revision=:r "
            "AND status IN ('open','review') AND deleted_at IS NULL AND EXISTS "
            "(SELECT 1 FROM companion_artifacts WHERE tenant_id=:t AND owner_id=:o "
            "AND slug=:slug AND deleted_at IS NULL)",
            {"now": now, "t": tenant, "o": owner, "slug": slug,
             "id": comment_id, "r": expected},
        )
        return self.get_comment(tenant, owner, slug, comment_id) if result.row_count else None

    def delete_comment(self, tenant: str, owner: str, slug: str,
                       comment_id: str, expected: int, now: str) -> bool:
        return self._sql.execute(
            "UPDATE artifact_comments SET deleted_at=:now,revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND slug=:slug "
            "AND id=:id AND revision=:r AND deleted_at IS NULL AND EXISTS "
            "(SELECT 1 FROM companion_artifacts WHERE tenant_id=:t AND owner_id=:o "
            "AND slug=:slug AND deleted_at IS NULL)",
            {"now": now, "t": tenant, "o": owner, "slug": slug,
             "id": comment_id, "r": expected},
        ).row_count == 1


__all__ = ["CommentSQLMixin", "init_comments"]
