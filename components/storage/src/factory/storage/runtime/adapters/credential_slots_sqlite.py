"""Encrypted, mutable, generation-fenced credential-slot data plane.

MUTABLE store (generation fence + optimistic version), unlike the immutable
content-addressed protected-artifact store. Plaintext exists only transiently
during write/read/rekey; at rest only ciphertext lives in SQLite. Crypto is
delegated to ``SlotCodec`` (AES-256-GCM envelope, identity-bound AAD).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from factory.mcp_utils.interface import ProtectedContentKeyProvider

from ..ports.credential_slots import (
    CredentialSlotError, DecryptedSlot, SlotIdentity, SlotReceipt,
)
from .credential_slots_codec import SlotCodec

_PK = ("tenant_id", "owner_id", "provider_id", "connection_ref", "slot_kind")
_WHERE = " AND ".join(f"{name}=?" for name in _PK)


class SQLiteCredentialSlotStore:
    """Owner/tenant/provider/connection-scoped encrypted secret slots."""

    def __init__(self, db_path: str, keys: ProtectedContentKeyProvider) -> None:
        self._path, self._codec = db_path, SlotCodec(keys)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS credential_slots (
                tenant_id TEXT, owner_id TEXT, provider_id TEXT, connection_ref TEXT,
                slot_kind TEXT, generation INTEGER NOT NULL, version INTEGER NOT NULL,
                envelope TEXT NOT NULL, tombstoned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, owner_id, provider_id, connection_ref, slot_kind))""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10, isolation_level=None)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _key(ident: SlotIdentity) -> tuple[str, ...]:
        return tuple(getattr(ident, name) for name in _PK)

    def write(self, identity: SlotIdentity, secret: Mapping[str, Any], *,
              generation: int, expected_version: int | None) -> SlotReceipt:
        try:
            with self._conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    f"SELECT generation,version,tombstoned FROM credential_slots WHERE {_WHERE}",
                    self._key(identity)).fetchone()
                receipt = (self._create(conn, identity, generation, row, secret)
                           if expected_version is None
                           else self._rotate(conn, identity, generation, expected_version, row, secret))
                conn.execute("COMMIT")
                return receipt
        except CredentialSlotError:
            raise
        except Exception as exc:
            raise CredentialSlotError("credential slot unavailable") from exc

    def _create(self, conn: sqlite3.Connection, ident: SlotIdentity, generation: int,
                row: Any, secret: Mapping[str, Any]) -> SlotReceipt:
        expected = row[0] if (row and row[2]) else 1
        if (row and not row[2]) or generation != expected:
            raise CredentialSlotError("credential slot unavailable")
        envelope, now = self._codec.seal(ident, generation, 1, secret), self._now()
        conn.execute(
            "INSERT OR REPLACE INTO credential_slots VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (*self._key(ident), generation, 1, envelope, now, now))
        return SlotReceipt(generation=generation, version=1)

    def _rotate(self, conn: sqlite3.Connection, ident: SlotIdentity, generation: int,
                expected_version: int, row: Any, secret: Mapping[str, Any]) -> SlotReceipt:
        if not row or row[2] or row[0] != generation or row[1] != expected_version:
            raise CredentialSlotError("credential slot unavailable")
        envelope = self._codec.seal(ident, generation, expected_version + 1, secret)
        updated = conn.execute(
            f"UPDATE credential_slots SET version=?,envelope=?,updated_at=? WHERE {_WHERE} "
            "AND generation=? AND version=? AND tombstoned=0",
            (expected_version + 1, envelope, self._now(), *self._key(ident), generation, expected_version))
        if updated.rowcount != 1:
            raise CredentialSlotError("credential slot unavailable")
        return SlotReceipt(generation=generation, version=expected_version + 1)

    def read(self, identity: SlotIdentity, *, generation: int) -> DecryptedSlot:
        try:
            with self._conn() as conn:
                row = conn.execute(
                    f"SELECT generation,version,tombstoned,envelope FROM credential_slots WHERE {_WHERE}",
                    self._key(identity)).fetchone()
            if not row or row[2] or row[0] != generation:
                raise CredentialSlotError("credential slot unavailable")
            secret = self._codec.open(identity, row[0], row[1], row[3])
            return DecryptedSlot(secret=secret, generation=row[0], version=row[1])
        except CredentialSlotError:
            raise
        except Exception as exc:
            raise CredentialSlotError("credential slot unavailable") from exc

    def revoke(self, identity: SlotIdentity, *, generation: int) -> SlotReceipt:
        try:
            with self._conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                updated = conn.execute(
                    f"UPDATE credential_slots SET tombstoned=1,generation=generation+1,updated_at=? "
                    f"WHERE {_WHERE} AND generation=? AND tombstoned=0",
                    (self._now(), *self._key(identity), generation))
                row = conn.execute(
                    f"SELECT generation,version FROM credential_slots WHERE {_WHERE}",
                    self._key(identity)).fetchone()
                conn.execute("COMMIT")
            if updated.rowcount != 1 or not row:
                raise CredentialSlotError("credential slot unavailable")
            return SlotReceipt(generation=row[0], version=row[1])
        except CredentialSlotError:
            raise
        except Exception as exc:
            raise CredentialSlotError("credential slot unavailable") from exc

    def rekey(self, identity: SlotIdentity, *, generation: int) -> SlotReceipt:
        try:
            with self._conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    f"SELECT generation,version,tombstoned,envelope FROM credential_slots WHERE {_WHERE}",
                    self._key(identity)).fetchone()
                if not row or row[2] or row[0] != generation:
                    raise CredentialSlotError("credential slot unavailable")
                secret = self._codec.open(identity, row[0], row[1], row[3])
                envelope = self._codec.seal(identity, row[0], row[1], secret)
                updated = conn.execute(
                    f"UPDATE credential_slots SET envelope=?,updated_at=? WHERE {_WHERE} "
                    "AND generation=? AND version=? AND envelope=? AND tombstoned=0",
                    (envelope, self._now(), *self._key(identity), row[0], row[1], row[3]))
                if updated.rowcount != 1:
                    raise CredentialSlotError("credential slot unavailable")
                conn.execute("COMMIT")
            return SlotReceipt(generation=row[0], version=row[1])
        except CredentialSlotError:
            raise
        except Exception as exc:
            raise CredentialSlotError("credential slot unavailable") from exc


__all__ = ["SQLiteCredentialSlotStore"]
