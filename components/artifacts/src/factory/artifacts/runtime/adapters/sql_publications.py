"""Owner-scoped publication-notice persistence (feature-map row 67)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from factory.storage.interface import SQLStore

from ..models import PublicationNotice

NOTICE_SCHEMA = """CREATE TABLE IF NOT EXISTS artifact_publications (
 tenant_id TEXT NOT NULL,owner_id TEXT NOT NULL,slug TEXT NOT NULL,
 provider TEXT NOT NULL,external_ref TEXT NOT NULL,status TEXT NOT NULL,
 detail TEXT NOT NULL,revision INTEGER NOT NULL,published_at TEXT NOT NULL,
 last_checked_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id,owner_id,slug,provider))"""


def init_publications(sql: SQLStore) -> None:
    sql.execute(NOTICE_SCHEMA)


def notice_from(row: dict[str, Any] | None) -> PublicationNotice | None:
    if row is None:
        return None
    value = dict(row)
    value["published_at"] = datetime.fromisoformat(value["published_at"])
    value["last_checked_at"] = datetime.fromisoformat(value["last_checked_at"])
    return PublicationNotice.model_validate(value)


class PublicationSQLMixin:
    _sql: SQLStore

    def upsert_publication(
        self, tenant: str, owner: str, slug: str, provider: str,
        external_ref: str, detail: str, now: str,
    ) -> PublicationNotice | None:
        self._sql.execute(
            "INSERT INTO artifact_publications (tenant_id,owner_id,slug,provider,"
            "external_ref,status,detail,revision,published_at,last_checked_at) "
            "SELECT :t,:o,:slug,:provider,:ref,'published',:detail,1,:now,:now "
            "WHERE EXISTS (SELECT 1 FROM companion_artifacts WHERE tenant_id=:t "
            "AND owner_id=:o AND slug=:slug AND deleted_at IS NULL) "
            "ON CONFLICT (tenant_id,owner_id,slug,provider) DO UPDATE SET "
            "external_ref=:ref,status='published',detail=:detail,"
            "revision=revision+1,published_at=:now,last_checked_at=:now",
            {"t": tenant, "o": owner, "slug": slug, "provider": provider,
             "ref": external_ref, "detail": detail, "now": now},
        )
        return self.get_publication(tenant, owner, slug, provider)

    def get_publication(
        self, tenant: str, owner: str, slug: str, provider: str,
    ) -> PublicationNotice | None:
        return notice_from(self._sql.fetch_one(
            "SELECT * FROM artifact_publications WHERE tenant_id=:t "
            "AND owner_id=:o AND slug=:slug AND provider=:provider",
            {"t": tenant, "o": owner, "slug": slug, "provider": provider},
        ))

    def update_publication_status(
        self, tenant: str, owner: str, slug: str, provider: str,
        status: str, detail: str, now: str,
    ) -> PublicationNotice | None:
        self._sql.execute(
            "UPDATE artifact_publications SET status=:status,detail=:detail,"
            "revision=revision+1,last_checked_at=:now WHERE tenant_id=:t "
            "AND owner_id=:o AND slug=:slug AND provider=:provider",
            {"status": status, "detail": detail, "now": now,
             "t": tenant, "o": owner, "slug": slug, "provider": provider},
        )
        return self.get_publication(tenant, owner, slug, provider)

    def remove_publication(
        self, tenant: str, owner: str, slug: str, provider: str,
    ) -> bool:
        return self._sql.execute(
            "DELETE FROM artifact_publications WHERE tenant_id=:t "
            "AND owner_id=:o AND slug=:slug AND provider=:provider",
            {"t": tenant, "o": owner, "slug": slug, "provider": provider},
        ).row_count == 1


__all__ = ["PublicationSQLMixin", "init_publications"]
