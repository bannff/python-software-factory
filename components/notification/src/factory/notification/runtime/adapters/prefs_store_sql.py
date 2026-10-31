"""Durable owner-scoped notification preferences over public Storage SQLStore."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from factory.storage.interface import SQLStore, get_sql_store

from ..inbox_models import Priority, RevisionConflictError
from ..prefs_models import NotificationPreferences

_DDL = """CREATE TABLE IF NOT EXISTS notification_prefs (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
    global_muted INTEGER NOT NULL DEFAULT 0,
    muted_kinds_json TEXT NOT NULL DEFAULT '[]',
    priority_overrides_json TEXT NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, owner_id))"""


def _snapshot(row: dict) -> NotificationPreferences:
    overrides = {
        kind: Priority(value)
        for kind, value in json.loads(row["priority_overrides_json"]).items()
    }
    return NotificationPreferences(
        tenant_id=row["tenant_id"], owner_id=row["owner_id"],
        global_muted=bool(row["global_muted"]),
        muted_kinds=frozenset(json.loads(row["muted_kinds_json"])),
        priority_overrides=overrides, revision=int(row["revision"]),
    )


class SqlPreferencesStore:
    """SQLStore-backed full-replace preference snapshots."""

    def __init__(
        self, sql: SQLStore | None = None, *,
        db_path: str = "./.storage/notification.db",
    ) -> None:
        self._sql = sql or get_sql_store("sqlite", db_path=db_path)
        self.initialize()

    def initialize(self) -> None:
        self._sql.execute(_DDL)

    def get(self, tenant_id: str, owner_id: str) -> NotificationPreferences:
        row = self._sql.fetch_one(
            "SELECT * FROM notification_prefs WHERE tenant_id=:t AND owner_id=:o",
            {"t": tenant_id, "o": owner_id},
        )
        return _snapshot(row) if row else NotificationPreferences(
            tenant_id=tenant_id, owner_id=owner_id,
        )

    def put(
        self, preferences: NotificationPreferences, *, expected_revision: int,
    ) -> NotificationPreferences:
        params = self._params(preferences, expected_revision)
        updated = self._sql.execute(
            "UPDATE notification_prefs SET global_muted=:muted, "
            "muted_kinds_json=:kinds, priority_overrides_json=:priorities, "
            "revision=revision+1, updated_at=:updated "
            "WHERE tenant_id=:t AND owner_id=:o AND revision=:expected",
            params,
        )
        if updated.row_count != 1 and expected_revision == 1:
            updated = self._sql.execute(
                "INSERT OR IGNORE INTO notification_prefs "
                "(tenant_id,owner_id,global_muted,muted_kinds_json,"
                "priority_overrides_json,revision,updated_at) VALUES "
                "(:t,:o,:muted,:kinds,:priorities,2,:updated)",
                params,
            )
        if updated.row_count != 1:
            raise RevisionConflictError()
        return self.get(preferences.tenant_id, preferences.owner_id)

    @staticmethod
    def _params(
        preferences: NotificationPreferences, expected_revision: int,
    ) -> dict:
        return {
            "t": preferences.tenant_id, "o": preferences.owner_id,
            "muted": int(preferences.global_muted),
            "kinds": json.dumps(sorted(preferences.muted_kinds), separators=(",", ":")),
            "priorities": json.dumps(
                {key: value.value for key, value in sorted(
                    preferences.priority_overrides.items())}, separators=(",", ":")),
            "expected": expected_revision,
            "updated": datetime.now(timezone.utc).isoformat(),
        }


__all__ = ["SqlPreferencesStore"]
