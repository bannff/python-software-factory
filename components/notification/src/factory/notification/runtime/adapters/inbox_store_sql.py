"""Owner-scoped durable notification inbox over public Storage SQLStore.

Uses only ``factory.storage.interface`` (no Storage runtime internals). Dedupe
identity is ``(tenant, owner, dedupe_key)``: an identical replay is a no-op,
different content under the same key conflicts without overwrite. Mark
read/unread are single-statement revision-CAS updates. A fresh instance over
the same DB path resumes all rows (restart continuity).
"""
from __future__ import annotations

from datetime import datetime, timezone

from factory.storage.interface import SQLStore, get_sql_store

from ..inbox_models import (
    InboxAdapterError, InboxCommit, InboxCommitStatus, NotificationNotFoundError,
    NotificationRecord, Priority, RevisionConflictError, UnreadCountConflictError,
)
from ..inbox_targets import build_target, target_id, target_kind

_DDL = """CREATE TABLE IF NOT EXISTS notification_inbox (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, notification_id TEXT NOT NULL,
    kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL, content_digest TEXT NOT NULL,
    created_at TEXT NOT NULL, read_at TEXT, revision INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tenant_id, owner_id, notification_id),
    UNIQUE (tenant_id, owner_id, dedupe_key))"""

_INSERT = """INSERT OR IGNORE INTO notification_inbox
    (tenant_id, owner_id, notification_id, kind, title, body, priority,
     target_kind, target_id, dedupe_key, content_digest, created_at, read_at,
     revision)
    VALUES (:tenant_id, :owner_id, :notification_id, :kind, :title, :body,
     :priority, :target_kind, :target_id, :dedupe_key, :content_digest,
     :created_at, :read_at, :revision)"""


def _record(row: dict) -> NotificationRecord:
    return NotificationRecord(
        tenant_id=row["tenant_id"], owner_id=row["owner_id"],
        notification_id=row["notification_id"], kind=row["kind"],
        title=row["title"], body=row["body"], priority=Priority(row["priority"]),
        target=build_target(row["target_kind"], row["target_id"]),
        dedupe_key=row["dedupe_key"],
        created_at=datetime.fromisoformat(row["created_at"]),
        read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
        revision=int(row["revision"]))


class SqlInboxStore:
    """SQLStore-backed :class:`InboxStore`."""

    def __init__(self, sql: SQLStore | None = None, *,
                 db_path: str = "./.storage/notification.db") -> None:
        self._sql = sql or get_sql_store("sqlite", db_path=db_path)
        self.initialize()

    def initialize(self) -> None:
        self._sql.execute(_DDL)

    def create_or_replay(self, record: NotificationRecord) -> InboxCommit:
        params = {
            "tenant_id": record.tenant_id, "owner_id": record.owner_id,
            "notification_id": record.notification_id, "kind": record.kind,
            "title": record.title, "body": record.body,
            "priority": record.priority.value,
            "target_kind": target_kind(record.target),
            "target_id": target_id(record.target), "dedupe_key": record.dedupe_key,
            "content_digest": record.content_digest,
            "created_at": record.created_at.isoformat(),
            "read_at": record.read_at.isoformat() if record.read_at else None,
            "revision": record.revision,
        }
        res = self._sql.execute(_INSERT, params)
        if res.row_count == 1:
            return InboxCommit(status=InboxCommitStatus.CREATED, record=record)
        existing = self._by_dedupe(record.tenant_id, record.owner_id,
                                   record.dedupe_key)
        if existing is None:
            raise InboxAdapterError("notification inbox commit unavailable")
        status = (InboxCommitStatus.REPLAYED
                  if existing.content_digest == record.content_digest
                  else InboxCommitStatus.CONFLICT)
        return InboxCommit(status=status, record=existing)

    def get(self, tenant_id: str, owner_id: str,
            notification_id: str) -> NotificationRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM notification_inbox WHERE tenant_id=:t AND owner_id=:o "
            "AND notification_id=:n",
            {"t": tenant_id, "o": owner_id, "n": notification_id})
        return _record(row) if row else None

    def list(self, tenant_id: str, owner_id: str, *, limit: int, offset: int = 0,
             unread_only: bool = False) -> list[NotificationRecord]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid inbox page")
        q = ("SELECT * FROM notification_inbox WHERE tenant_id=:t AND owner_id=:o")
        if unread_only:
            q += " AND read_at IS NULL"
        q += " ORDER BY created_at DESC, notification_id DESC LIMIT :lim OFFSET :off"
        rows = self._sql.fetch_all(
            q, {"t": tenant_id, "o": owner_id, "lim": limit, "off": offset})
        return [_record(row) for row in rows]

    def mark_read(self, tenant_id: str, owner_id: str, notification_id: str, *,
                  expected_revision: int, read_at: datetime) -> NotificationRecord:
        if read_at.tzinfo is None or read_at.utcoffset() is None:
            raise ValueError("notification read timestamp must be timezone-aware")
        return self._cas_mark(tenant_id, owner_id, notification_id,
                              expected_revision, read_at.astimezone(timezone.utc).isoformat())

    def mark_unread(self, tenant_id: str, owner_id: str, notification_id: str, *,
                    expected_revision: int) -> NotificationRecord:
        return self._cas_mark(tenant_id, owner_id, notification_id,
                              expected_revision, None)

    def mark_all_read(self, tenant_id: str, owner_id: str, *,
                      expected_unread_count: int, read_at: datetime) -> int:
        """Single fenced statement: mark every unread row read only when the
        live unread count equals ``expected_unread_count``. The scalar subquery
        is uncorrelated (bound params only), so SQLite evaluates it once before
        applying the update — the mark is all-or-nothing, never partial."""
        if read_at.tzinfo is None or read_at.utcoffset() is None:
            raise ValueError("notification read timestamp must be timezone-aware")
        ts = read_at.astimezone(timezone.utc).isoformat()
        res = self._sql.execute(
            "UPDATE notification_inbox SET read_at=:r, revision=revision+1 "
            "WHERE tenant_id=:t AND owner_id=:o AND read_at IS NULL AND ("
            "SELECT COUNT(*) FROM notification_inbox "
            "WHERE tenant_id=:t AND owner_id=:o AND read_at IS NULL)=:exp",
            {"r": ts, "t": tenant_id, "o": owner_id, "exp": expected_unread_count})
        # Fence matched iff exactly ``expected`` unread rows transitioned. The
        # zero case is ambiguous (mismatch also yields 0), so re-check the count.
        if res.row_count == expected_unread_count and (
            expected_unread_count != 0
            or self._unread_count(tenant_id, owner_id) == 0
        ):
            return res.row_count
        raise UnreadCountConflictError()

    def _unread_count(self, tenant_id: str, owner_id: str) -> int:
        row = self._sql.fetch_one(
            "SELECT COUNT(*) AS n FROM notification_inbox "
            "WHERE tenant_id=:t AND owner_id=:o AND read_at IS NULL",
            {"t": tenant_id, "o": owner_id})
        return int(row["n"]) if row else 0

    def _cas_mark(self, tenant_id: str, owner_id: str, notification_id: str,
                  expected_revision: int, read_at: str | None) -> NotificationRecord:
        res = self._sql.execute(
            "UPDATE notification_inbox SET read_at=:r, revision=revision+1 "
            "WHERE tenant_id=:t AND owner_id=:o AND notification_id=:n "
            "AND revision=:rev",
            {"r": read_at, "t": tenant_id, "o": owner_id, "n": notification_id,
             "rev": expected_revision})
        if res.row_count == 1:
            got = self.get(tenant_id, owner_id, notification_id)
            if got is not None:
                return got
        # CAS miss: distinguish stale revision from foreign/absent — both opaque.
        if self.get(tenant_id, owner_id, notification_id) is None:
            raise NotificationNotFoundError()
        raise RevisionConflictError()

    def _by_dedupe(self, tenant_id: str, owner_id: str,
                   dedupe_key: str) -> NotificationRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM notification_inbox WHERE tenant_id=:t AND owner_id=:o "
            "AND dedupe_key=:d",
            {"t": tenant_id, "o": owner_id, "d": dedupe_key})
        return _record(row) if row else None


__all__ = ["SqlInboxStore"]
