"""Owner-scoped durable migration receipts over public Storage SQLStore."""
from __future__ import annotations

from factory.storage.interface import SQLStore, get_sql_store

from ..receipt_models import (
    CommitStatus, CursorConflictError, ImportOutcome, ImportReceipt, PageCursor,
    ReceiptCommit,
)
from .plan_store_sql import PlanStoreSqlMixin

_RECEIPTS = """CREATE TABLE IF NOT EXISTS migration_receipts (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, adapter TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL, kind TEXT NOT NULL,
    source_record_id TEXT NOT NULL, target_digest TEXT NOT NULL,
    outcome TEXT NOT NULL, reason_code TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tenant_id, owner_id, adapter, source_fingerprint, kind, source_record_id))"""
_CURSORS = """CREATE TABLE IF NOT EXISTS migration_plan_cursors (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, adapter TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL, plan_digest TEXT NOT NULL, kind TEXT NOT NULL,
    page_index INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tenant_id, owner_id, adapter, source_fingerprint, plan_digest, kind))"""

_R_COLS = ("tenant_id", "owner_id", "adapter", "source_fingerprint", "kind",
           "source_record_id", "target_digest", "outcome", "reason_code", "revision")


def _receipt(row) -> ImportReceipt:
    values = {c: ImportOutcome(row[c]) if c == "outcome" else row[c] for c in _R_COLS}
    return ImportReceipt(**values)


class SqlReceiptStore(PlanStoreSqlMixin):

    def __init__(self, sql: SQLStore | None = None, *,
                 db_path: str = "./.storage/migration.db") -> None:
        self._sql = sql or get_sql_store("sqlite", db_path=db_path)
        self.initialize()

    def initialize(self) -> None:
        for ddl in (_RECEIPTS, _CURSORS):
            self._sql.execute(ddl)
        self._initialize_plans()

    def record_receipt(self, receipt: ImportReceipt) -> ReceiptCommit:
        params = receipt.model_dump(mode="json")
        res = self._sql.execute(
            "INSERT OR IGNORE INTO migration_receipts (tenant_id, owner_id, adapter, "
            "source_fingerprint, kind, source_record_id, target_digest, outcome, "
            "reason_code, revision) VALUES (:tenant_id, :owner_id, :adapter, "
            ":source_fingerprint, :kind, :source_record_id, :target_digest, "
            ":outcome, :reason_code, :revision)", params)
        if res.row_count == 1:
            return ReceiptCommit(status=CommitStatus.COMMITTED, receipt=receipt)
        existing = self._find(receipt)
        if existing is None:
            return ReceiptCommit(status=CommitStatus.COMMITTED, receipt=receipt)
        if not existing.outcome.is_settled:
            nxt = existing.revision + 1
            upd = self._sql.execute(
                "UPDATE migration_receipts SET target_digest=:target_digest, "
                "outcome=:outcome, reason_code=:reason_code, revision=:nxt "
                "WHERE tenant_id=:tenant_id AND owner_id=:owner_id AND adapter=:adapter "
                "AND source_fingerprint=:source_fingerprint AND kind=:kind AND "
                "source_record_id=:source_record_id AND revision=:expected",
                {**params, "nxt": nxt, "expected": existing.revision})
            if upd.row_count == 1:
                return ReceiptCommit(status=CommitStatus.SUPERSEDED,
                                     receipt=receipt.model_copy(update={"revision": nxt}))
            existing = self._find(receipt)  # concurrent change; re-read
            if existing is None:
                return ReceiptCommit(status=CommitStatus.COMMITTED, receipt=receipt)
        status = (CommitStatus.REPLAYED if existing.target_digest == receipt.target_digest
                  else CommitStatus.CONFLICT)
        return ReceiptCommit(status=status, receipt=existing)

    def find_receipt(self, tenant_id: str, owner_id: str, adapter: str,
                     source_fingerprint: str, kind: str,
                     source_record_id: str) -> ImportReceipt | None:
        row = self._sql.fetch_one(
            "SELECT * FROM migration_receipts WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint AND kind=:kind AND "
            "source_record_id=:source_record_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint, "kind": kind,
             "source_record_id": source_record_id})
        return _receipt(row) if row else None

    def _find(self, r: ImportReceipt) -> ImportReceipt | None:
        return self.find_receipt(r.tenant_id, r.owner_id, r.adapter,
                                 r.source_fingerprint, r.kind, r.source_record_id)

    def list_receipts(self, tenant_id: str, owner_id: str, adapter: str,
                      source_fingerprint: str,
                      kind: str | None = None) -> list[ImportReceipt]:
        q = ("SELECT * FROM migration_receipts WHERE tenant_id=:tenant_id AND "
             "owner_id=:owner_id AND adapter=:adapter AND "
             "source_fingerprint=:source_fingerprint")
        p = {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint}
        if kind is not None:
            q += " AND kind=:kind"
            p["kind"] = kind
        rows = self._sql.fetch_all(q + " ORDER BY kind, source_record_id", p)
        return [_receipt(row) for row in rows]

    def outcome_counts(self, tenant_id: str, owner_id: str, adapter: str,
                       source_fingerprint: str) -> dict[str, int]:
        rows = self._sql.fetch_all(
            "SELECT outcome, COUNT(*) AS n FROM migration_receipts WHERE "
            "tenant_id=:tenant_id AND owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint GROUP BY outcome",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint})
        return {row["outcome"]: int(row["n"]) for row in rows}

    def load_cursor(self, tenant_id: str, owner_id: str, adapter: str,
                    source_fingerprint: str, plan_digest: str,
                    kind: str) -> PageCursor | None:
        row = self._sql.fetch_one(
            "SELECT * FROM migration_plan_cursors WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint AND plan_digest=:plan_digest "
            "AND kind=:kind",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint, "plan_digest": plan_digest,
             "kind": kind})
        if not row:
            return None
        return PageCursor(
            tenant_id=row["tenant_id"], owner_id=row["owner_id"], adapter=row["adapter"],
            source_fingerprint=row["source_fingerprint"], plan_digest=row["plan_digest"],
            kind=row["kind"],
            page_index=int(row["page_index"]), revision=int(row["revision"]))

    def save_cursor(self, cursor: PageCursor,
                    expected_revision: int | None = None) -> PageCursor:
        if expected_revision is None:
            params = cursor.model_dump(mode="json")
            params["revision"] = 1
            res = self._sql.execute(
                "INSERT OR IGNORE INTO migration_plan_cursors (tenant_id, owner_id, "
                "adapter, source_fingerprint, plan_digest, kind, page_index, revision) "
                "VALUES (:tenant_id, :owner_id, :adapter, :source_fingerprint, "
                ":plan_digest, :kind, :page_index, :revision)", params)
            if res.row_count == 1:
                return cursor.model_copy(update={"revision": 1})
            raise CursorConflictError("cursor already exists")
        nxt = expected_revision + 1
        res = self._sql.execute(
            "UPDATE migration_plan_cursors SET page_index=:page_index, revision=:nxt "
            "WHERE tenant_id=:tenant_id AND owner_id=:owner_id AND adapter=:adapter "
            "AND source_fingerprint=:source_fingerprint AND plan_digest=:plan_digest "
            "AND kind=:kind AND revision=:expected",
            {"page_index": cursor.page_index, "nxt": nxt, "expected": expected_revision,
             "tenant_id": cursor.tenant_id, "owner_id": cursor.owner_id,
             "adapter": cursor.adapter, "source_fingerprint": cursor.source_fingerprint,
             "plan_digest": cursor.plan_digest, "kind": cursor.kind})
        if res.row_count == 1:
            return cursor.model_copy(update={"revision": nxt})
        raise CursorConflictError("stale cursor revision")


__all__ = ["SqlReceiptStore"]
