"""SQLStore adapter for origin-session background completion delivery."""
from __future__ import annotations

from typing import Any

from factory.storage.interface import SQLStore

from ..models import CompletionDelivery

_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_completions (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, session_id TEXT NOT NULL,
 run_id TEXT NOT NULL, outcome TEXT NOT NULL, summary TEXT NOT NULL,
 result_digest TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
 delivered_at TEXT, revision INTEGER NOT NULL,
 PRIMARY KEY (tenant_id, owner_id, session_id, run_id)
)
"""
_FIELDS = (
    "tenant_id", "owner_id", "session_id", "run_id", "outcome", "summary",
    "result_digest", "state", "created_at", "delivered_at", "revision",
)


class SQLCompletionStore:
    def __init__(self, sql: SQLStore) -> None:
        self._sql = sql
        sql.execute(_SCHEMA)

    def append(self, delivery: CompletionDelivery) -> CompletionDelivery:
        columns = ",".join(_FIELDS)
        values = ",".join(f":{field}" for field in _FIELDS)
        self._sql.execute(
            f"INSERT INTO session_completions ({columns}) SELECT {values} "
            "WHERE EXISTS (SELECT 1 FROM companion_sessions WHERE "
            "tenant_id=:tenant_id AND owner_id=:owner_id AND session_id=:session_id) "
            "ON CONFLICT (tenant_id,owner_id,session_id,run_id) DO NOTHING",
            delivery.model_dump(mode="json"),
        )
        existing = self.get(
            delivery.tenant_id, delivery.owner_id,
            delivery.session_id, delivery.run_id,
        )
        if existing is None:
            raise ValueError("session not found")
        if existing.result_digest != delivery.result_digest:
            raise ValueError("completion binding conflict")
        return existing

    def get(
        self, tenant_id: str, owner_id: str, session_id: str, run_id: str,
    ) -> CompletionDelivery | None:
        row = self._sql.fetch_one(
            "SELECT * FROM session_completions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id AND run_id=:run_id",
            _identity(tenant_id, owner_id, session_id, run_id),
        )
        return CompletionDelivery.model_validate(row) if row else None

    def has_pending(self, tenant_id: str, owner_id: str, session_id: str) -> bool:
        row = self._sql.fetch_one(
            "SELECT 1 AS present FROM session_completions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id AND state='pending' LIMIT 1",
            _identity(tenant_id, owner_id, session_id),
        )
        return row is not None

    def list_pending(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> list[CompletionDelivery]:
        rows = self._sql.fetch_all(
            "SELECT * FROM session_completions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id AND state='pending' "
            "ORDER BY created_at,run_id",
            _identity(tenant_id, owner_id, session_id),
        )
        return [CompletionDelivery.model_validate(row) for row in rows]

    def mark_delivered(
        self, tenant_id: str, owner_id: str, session_id: str, run_id: str,
        result_digest: str, revision: int, delivered_at: str,
    ) -> CompletionDelivery | None:
        result = self._sql.execute(
            "UPDATE session_completions SET state='delivered',delivered_at=:delivered_at,"
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND run_id=:run_id AND result_digest=:result_digest "
            "AND revision=:revision AND state='pending'",
            {**_identity(tenant_id, owner_id, session_id, run_id),
             "result_digest": result_digest, "revision": revision,
             "delivered_at": delivered_at},
        )
        value = self.get(tenant_id, owner_id, session_id, run_id)
        return value if result.row_count == 1 else None


def _identity(
    tenant_id: str, owner_id: str, session_id: str, run_id: str | None = None,
) -> dict[str, Any]:
    values = {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id}
    if run_id is not None:
        values["run_id"] = run_id
    return values


__all__ = ["SQLCompletionStore"]
