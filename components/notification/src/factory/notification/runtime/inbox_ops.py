"""Owner-scoped inbox read/mark operations over an :class:`InboxStore`.

Thin runtime layer between the MCP tools and the durable store. It supplies
the UTC ``read_at`` clock for mark writes and turns a foreign/absent ``get``
into the opaque :class:`NotificationNotFoundError`, so the store stays a pure
persistence port and the tools stay pure transport. All reads/writes are
already tenant+owner scoped by the caller-derived ambient identity.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .inbox_models import NotificationNotFoundError, NotificationRecord
from .ports import InboxStore


class InboxOperations:
    """Owner-scoped delegates over a durable :class:`InboxStore`."""

    def __init__(self, store: InboxStore) -> None:
        self._store = store

    def list(self, tenant_id: str, owner_id: str, *, limit: int = 50,
             offset: int = 0, unread_only: bool = False) -> list[NotificationRecord]:
        return self._store.list(tenant_id, owner_id, limit=limit, offset=offset,
                                unread_only=unread_only)

    def get(self, tenant_id: str, owner_id: str,
            notification_id: str) -> NotificationRecord:
        record = self._store.get(tenant_id, owner_id, notification_id)
        if record is None:
            raise NotificationNotFoundError()
        return record

    def mark_read(self, tenant_id: str, owner_id: str, notification_id: str, *,
                  expected_revision: int) -> NotificationRecord:
        return self._store.mark_read(
            tenant_id, owner_id, notification_id,
            expected_revision=expected_revision, read_at=_now())

    def mark_all_read(self, tenant_id: str, owner_id: str, *,
                      expected_unread_count: int) -> int:
        return self._store.mark_all_read(
            tenant_id, owner_id, expected_unread_count=expected_unread_count,
            read_at=_now())


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["InboxOperations"]
