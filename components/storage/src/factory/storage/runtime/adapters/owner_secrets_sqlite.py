"""Encrypted, mutable, owner-named secret KV — last-write-wins, no generation fence.

Plaintext exists only transiently inside set_secret(); at rest only ciphertext
lives in SQLite. AAD binds tenant_id + principal_id + name + key_id so a
sealed record cannot be replayed under a different owner or a different name
(ciphertext transplant is the exact attack the AAD binding rules out — matching
upstream's own ``_aad_for`` name-binding). No generation/version CAS: an
owner-managed KV has no second authority to invalidate on rotation, and adding
CAS here would be concurrency-failure surface with no security benefit
(see the row-98 architecture consult, amendment A2).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import ProtectedContentKeyProvider, protected_canonical_json

from ..ports.owner_secrets import OwnerSecretError, OwnerSecretIdentity
from .aead_envelope import AeadEnvelopeCodec

_NAME_MAX = 255


def _aad(ident: OwnerSecretIdentity, name: str, key_id: str) -> bytes:
    return protected_canonical_json({
        "v": "owner-secret-1", "tenant_id": ident.tenant_id,
        "principal_id": ident.principal_id, "name": name, "key_id": key_id,
    })


class SQLiteOwnerSecretStore:
    """Owner/tenant-scoped encrypted named secrets (PRIMARY KEY: tenant+principal+name)."""

    def __init__(self, db_path: str, keys: ProtectedContentKeyProvider) -> None:
        self._path, self._codec = db_path, AeadEnvelopeCodec(keys)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS owner_secrets (
                tenant_id TEXT NOT NULL, principal_id TEXT NOT NULL, name TEXT NOT NULL,
                envelope TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, principal_id, name))""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10, isolation_level=None)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def set_secret(self, ident: OwnerSecretIdentity, name: str, value: str) -> None:
        if not name or len(name) > _NAME_MAX or not isinstance(value, str):
            raise OwnerSecretError()
        try:
            envelope = self._codec.seal(
                lambda key_id: _aad(ident, name, key_id), {"value": value})
            now = self._now()
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO owner_secrets (tenant_id, principal_id, name, envelope, "
                    "created_at, updated_at) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(tenant_id, principal_id, name) "
                    "DO UPDATE SET envelope=excluded.envelope, updated_at=excluded.updated_at",
                    (ident.tenant_id, ident.principal_id, name, envelope, now, now))
        except OwnerSecretError:
            raise
        except Exception as exc:
            raise OwnerSecretError() from exc

    def delete_secret(self, ident: OwnerSecretIdentity, name: str) -> bool:
        try:
            with self._conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM owner_secrets WHERE tenant_id=? AND principal_id=? AND name=?",
                    (ident.tenant_id, ident.principal_id, name))
                return cursor.rowcount == 1
        except Exception as exc:
            raise OwnerSecretError() from exc

    def list_names(self, ident: OwnerSecretIdentity) -> list[str]:
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT name FROM owner_secrets WHERE tenant_id=? AND principal_id=? "
                    "ORDER BY name", (ident.tenant_id, ident.principal_id)).fetchall()
            return [row[0] for row in rows]
        except Exception as exc:
            raise OwnerSecretError() from exc


__all__ = ["SQLiteOwnerSecretStore"]
