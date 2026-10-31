"""Human-gated permanent artifact purge persistence."""
from __future__ import annotations

from factory.storage.interface import SQLStore

PURGE_TRIGGER = """CREATE TRIGGER IF NOT EXISTS artifact_authoring_purge
 AFTER UPDATE OF purge_token ON companion_artifacts
 WHEN NEW.purge_token IS NOT NULL BEGIN
 DELETE FROM artifact_comments WHERE tenant_id=NEW.tenant_id
  AND owner_id=NEW.owner_id AND slug=NEW.slug;
 DELETE FROM artifact_versions WHERE tenant_id=NEW.tenant_id
  AND owner_id=NEW.owner_id AND slug=NEW.slug;
 DELETE FROM companion_artifacts WHERE tenant_id=NEW.tenant_id
  AND owner_id=NEW.owner_id AND slug=NEW.slug;
 END"""


def init_purge(sql: SQLStore) -> None:
    sql.execute(PURGE_TRIGGER)


class AuthoringSQLMixin:
    _sql: SQLStore

    def purge_artifact(self, tenant: str, owner: str, slug: str,
                       expected: int, token: str) -> bool:
        return self._sql.execute(
            "UPDATE companion_artifacts SET purge_token=:token "
            "WHERE tenant_id=:t AND owner_id=:o AND slug=:slug "
            "AND revision=:r AND deleted_at IS NOT NULL",
            {"token": token, "t": tenant, "o": owner,
             "slug": slug, "r": expected},
        ).row_count == 1


__all__ = ["AuthoringSQLMixin", "init_purge"]
