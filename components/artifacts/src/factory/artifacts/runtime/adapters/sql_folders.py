"""Owner-scoped artifact folder persistence."""
from __future__ import annotations

from typing import Any

from factory.storage.interface import SQLStore

from .sql_rows import folder_from

FOLDER_SCHEMA = """CREATE TABLE IF NOT EXISTS artifact_folders (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, id TEXT NOT NULL,
 parent_id TEXT, name TEXT NOT NULL, position INTEGER NOT NULL,
 revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 deleted_at TEXT, PRIMARY KEY (tenant_id,owner_id,id))"""
FOLDER_NAME_INDEX = """CREATE UNIQUE INDEX IF NOT EXISTS folder_active_name
 ON artifact_folders(tenant_id,owner_id,COALESCE(parent_id,''),name)
 WHERE deleted_at IS NULL"""
FOLDER_DELETE_TRIGGER = """CREATE TRIGGER IF NOT EXISTS folder_safe_delete
 AFTER UPDATE OF deleted_at ON artifact_folders
 WHEN OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL BEGIN
 UPDATE artifact_folders SET parent_id=OLD.parent_id,revision=revision+1,
  updated_at=NEW.updated_at WHERE tenant_id=OLD.tenant_id
  AND owner_id=OLD.owner_id AND parent_id=OLD.id AND deleted_at IS NULL;
 UPDATE companion_artifacts SET folder_id=OLD.parent_id,revision=revision+1,
  updated_at=NEW.updated_at,event_type='updated' WHERE tenant_id=OLD.tenant_id
  AND owner_id=OLD.owner_id AND folder_id=OLD.id AND deleted_at IS NULL;
 END"""


def init_folders(sql: SQLStore) -> None:
    for statement in (FOLDER_SCHEMA, FOLDER_NAME_INDEX, FOLDER_DELETE_TRIGGER):
        sql.execute(statement)


class FolderSQLMixin:
    _sql: SQLStore

    def create_folder(self, tenant: str, owner: str, folder_id: str,
                      name: str, parent_id: str | None, now: str):
        self._sql.execute(
            "INSERT OR IGNORE INTO artifact_folders SELECT :tenant,:owner,:id,"
            ":parent,:name,COALESCE((SELECT MAX(position)+1 FROM artifact_folders "
            "WHERE tenant_id=:tenant AND owner_id=:owner AND parent_id IS :parent "
            "AND deleted_at IS NULL),0),1,:now,:now,NULL WHERE (:parent IS NULL OR "
            "(SELECT COUNT(*) FROM (WITH RECURSIVE chain(id,parent_id) AS "
            "(SELECT id,parent_id FROM artifact_folders WHERE tenant_id=:tenant "
            "AND owner_id=:owner AND id=:parent AND deleted_at IS NULL UNION ALL "
            "SELECT f.id,f.parent_id FROM artifact_folders f JOIN chain c ON "
            "f.id=c.parent_id WHERE f.tenant_id=:tenant AND f.owner_id=:owner "
            "AND f.deleted_at IS NULL) SELECT id FROM chain)) BETWEEN 1 AND 19) "
            "AND (SELECT COUNT(*) FROM artifact_folders WHERE tenant_id=:tenant "
            "AND owner_id=:owner AND deleted_at IS NULL)<500",
            {"tenant": tenant, "owner": owner, "id": folder_id,
             "parent": parent_id, "name": name, "now": now},
        )
        return self.get_folder(tenant, owner, folder_id)

    def list_folders(self, tenant: str, owner: str):
        rows = self._sql.fetch_all(
            "WITH RECURSIVE tree(id,parent_id,name,position,revision,created_at,"
            "updated_at,path,depth) AS (SELECT id,parent_id,name,position,revision,"
            "created_at,updated_at,name,1 FROM artifact_folders WHERE tenant_id=:t "
            "AND owner_id=:o AND parent_id IS NULL AND deleted_at IS NULL UNION ALL "
            "SELECT f.id,f.parent_id,f.name,f.position,f.revision,f.created_at,"
            "f.updated_at,tree.path||'/'||f.name,tree.depth+1 FROM artifact_folders f "
            "JOIN tree ON f.parent_id=tree.id WHERE f.tenant_id=:t AND f.owner_id=:o "
            "AND f.deleted_at IS NULL) SELECT tree.*,(SELECT COUNT(*) FROM "
            "companion_artifacts a WHERE a.tenant_id=:t AND a.owner_id=:o AND "
            "a.folder_id=tree.id AND a.deleted_at IS NULL) item_count FROM tree "
            "ORDER BY path,position", {"t": tenant, "o": owner},
        )
        return [folder_from(row, tenant, owner) for row in rows]

    def get_folder(self, tenant: str, owner: str, folder_id: str):
        return next((f for f in self.list_folders(tenant, owner)
                     if f.id == folder_id), None)

    def rename_folder(self, tenant: str, owner: str, folder_id: str,
                      expected: int, name: str, now: str):
        result = self._sql.execute(
            "UPDATE OR IGNORE artifact_folders SET name=:name,revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND id=:id "
            "AND revision=:r AND deleted_at IS NULL",
            {"name": name, "now": now, "t": tenant, "o": owner,
             "id": folder_id, "r": expected},
        )
        return self.get_folder(tenant, owner, folder_id) if result.row_count else None

    def move_folder(self, tenant: str, owner: str, folder_id: str,
                    expected: int, parent_id: str | None, now: str):
        result = self._sql.execute(
            "WITH RECURSIVE sub(id,d) AS (SELECT id,1 FROM artifact_folders WHERE "
            "tenant_id=:t AND owner_id=:o AND id=:id AND deleted_at IS NULL UNION ALL "
            "SELECT f.id,sub.d+1 FROM artifact_folders f JOIN sub ON f.parent_id=sub.id "
            "WHERE f.tenant_id=:t AND f.owner_id=:o AND f.deleted_at IS NULL), "
            "tree(id,d) AS (SELECT id,1 FROM artifact_folders WHERE tenant_id=:t "
            "AND owner_id=:o AND parent_id IS NULL AND deleted_at IS NULL UNION ALL "
            "SELECT f.id,tree.d+1 FROM artifact_folders f JOIN tree ON f.parent_id=tree.id "
            "WHERE f.tenant_id=:t AND f.owner_id=:o AND f.deleted_at IS NULL) "
            "UPDATE OR IGNORE artifact_folders SET parent_id=:parent,revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND id=:id "
            "AND revision=:r AND deleted_at IS NULL AND (:parent IS NULL OR EXISTS "
            "(SELECT 1 FROM tree WHERE id=:parent)) AND NOT EXISTS "
            "(SELECT 1 FROM sub WHERE id=:parent) AND (SELECT MAX(d) FROM sub)+"
            "COALESCE((SELECT d FROM tree WHERE id=:parent),0)<=20 "
            "RETURNING revision,parent_id",
            {"t": tenant, "o": owner, "id": folder_id, "r": expected,
             "parent": parent_id, "now": now},
        )
        return self.get_folder(tenant, owner, folder_id) if result.rows else None

    def delete_folder(self, tenant: str, owner: str, folder_id: str,
                      expected: int, now: str) -> bool:
        return self._sql.execute(
            "UPDATE artifact_folders SET deleted_at=:now,revision=revision+1,"
            "updated_at=:now WHERE tenant_id=:t AND owner_id=:o AND id=:id "
            "AND revision=:r AND deleted_at IS NULL",
            {"now": now, "t": tenant, "o": owner,
             "id": folder_id, "r": expected},
        ).row_count == 1

    def move_artifact(self, tenant: str, owner: str, slug: str, expected: int,
                      folder_id: str | None, now: str):
        result = self._sql.execute(
            "UPDATE companion_artifacts SET folder_id=:folder,revision=revision+1,"
            "updated_at=:now,event_type='moved' WHERE tenant_id=:t AND owner_id=:o "
            "AND slug=:slug AND revision=:r AND deleted_at IS NULL AND "
            "(:folder IS NULL OR EXISTS (SELECT 1 FROM artifact_folders WHERE "
            "tenant_id=:t AND owner_id=:o AND id=:folder AND deleted_at IS NULL))",
            {"folder": folder_id, "now": now, "t": tenant, "o": owner,
             "slug": slug, "r": expected},
        )
        return self.get(tenant, owner, slug) if result.row_count else None


__all__ = ["FolderSQLMixin", "init_folders"]
