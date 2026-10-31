"""SQLite adapter for the owner-scoped external MCP server registry."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from ..models import ServerRecord, ServerSpec, StaleServer

_SCHEMA = """CREATE TABLE IF NOT EXISTS connections_servers (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, name TEXT NOT NULL,
 spec_json TEXT NOT NULL, revision INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id, owner_id, name)
)"""
_COLUMNS = "tenant_id, owner_id, name, spec_json, revision, created_at, updated_at"


class SqliteServerStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @staticmethod
    def _model(row: tuple) -> ServerRecord:
        return ServerRecord(
            tenant_id=str(row[0]), owner_id=str(row[1]), name=str(row[2]),
            spec=ServerSpec.model_validate(json.loads(str(row[3]))),
            revision=int(row[4]),
            created_at=datetime.fromisoformat(str(row[5])),
            updated_at=datetime.fromisoformat(str(row[6])),
        )

    def list(self, tenant_id: str, owner_id: str) -> tuple[ServerRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_COLUMNS} FROM connections_servers "
                "WHERE tenant_id=? AND owner_id=? ORDER BY name", (tenant_id, owner_id),
            ).fetchall()
        return tuple(self._model(row) for row in rows)

    def list_all(self) -> tuple[ServerRecord, ...]:
        """Every owner's servers — startup remount only; mounts are process-wide."""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_COLUMNS} FROM connections_servers ORDER BY tenant_id, owner_id, name",
            ).fetchall()
        return tuple(self._model(row) for row in rows)

    def get(self, tenant_id: str, owner_id: str, name: str) -> ServerRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM connections_servers "
                "WHERE tenant_id=? AND owner_id=? AND name=?", (tenant_id, owner_id, name),
            ).fetchone()
        return None if row is None else self._model(row)

    def upsert(
        self, tenant_id: str, owner_id: str, name: str, spec: ServerSpec,
        expected_revision: int | None,
    ) -> ServerRecord:
        now = datetime.now(timezone.utc)
        payload = spec.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT revision, created_at FROM connections_servers "
                "WHERE tenant_id=? AND owner_id=? AND name=?", (tenant_id, owner_id, name),
            ).fetchone()
            if expected_revision is None:
                if current is not None:
                    raise StaleServer("server already exists")
                connection.execute(
                    f"INSERT INTO connections_servers ({_COLUMNS}) VALUES (?,?,?,?,?,?,?)",
                    (tenant_id, owner_id, name, payload, 1, now.isoformat(), now.isoformat()),
                )
                return ServerRecord(
                    tenant_id=tenant_id, owner_id=owner_id, name=name, spec=spec,
                    revision=1, created_at=now, updated_at=now,
                )
            if current is None or int(current[0]) != expected_revision:
                raise StaleServer("stale server revision")
            changed = connection.execute(
                "UPDATE connections_servers SET spec_json=?, revision=?, updated_at=? "
                "WHERE tenant_id=? AND owner_id=? AND name=? AND revision=?",
                (payload, expected_revision + 1, now.isoformat(),
                 tenant_id, owner_id, name, expected_revision),
            ).rowcount
            if changed != 1:
                raise StaleServer("stale server revision")
            return ServerRecord(
                tenant_id=tenant_id, owner_id=owner_id, name=name, spec=spec,
                revision=expected_revision + 1,
                created_at=datetime.fromisoformat(str(current[1])), updated_at=now,
            )

    def remove(
        self, tenant_id: str, owner_id: str, name: str, expected_revision: int,
    ) -> bool:
        with self._lock, self._connect() as connection:
            changed = connection.execute(
                "DELETE FROM connections_servers "
                "WHERE tenant_id=? AND owner_id=? AND name=? AND revision=?",
                (tenant_id, owner_id, name, expected_revision),
            ).rowcount
        if changed != 1:
            raise StaleServer("stale server revision")
        return True


__all__ = ["SqliteServerStore"]
