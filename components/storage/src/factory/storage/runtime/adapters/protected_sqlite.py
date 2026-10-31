"""Encrypted local SQLite protected-artifact data plane."""
from __future__ import annotations

import base64
import hmac
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from factory.mcp_utils.interface import (
    AuthorizationAssertion, ProtectedArtifactRef, ProtectedContentDescriptor,
    ProtectedContentKeyProvider, ProtectedContentProjection, protected_canonical_json,
)
from factory.mcp_utils.protected_content import new_artifact_ref

_KEY_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_FIELDS = frozenset({"v", "key_id", "payload_nonce", "ciphertext", "wrap_nonce", "wrapped_dek"})


class ProtectedArtifactError(ValueError):
    """Opaque denial for missing, unauthorized, expired, or malformed artifacts."""


class SQLiteBusinessContentArtifactStore:
    """Immutable encrypted artifacts; plaintext exists only during materialization."""
    def __init__(self, db_path: str, keys: ProtectedContentKeyProvider) -> None:
        self._path, self._keys = db_path, keys
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS protected_artifacts (
                ref TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL,
                descriptor TEXT NOT NULL, envelope TEXT NOT NULL,
                tombstoned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10, isolation_level=None)

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _decode(value: Any, *, exact: int | None = None, minimum: int = 1) -> bytes:
        if not isinstance(value, str) or not _B64URL.fullmatch(value) or len(value) > 16384:
            raise ValueError("invalid envelope")
        try:
            decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except ValueError as exc:
            raise ValueError("invalid envelope") from exc
        if SQLiteBusinessContentArtifactStore._encode(decoded) != value or len(decoded) < minimum \
                or (exact is not None and len(decoded) != exact):
            raise ValueError("invalid envelope")
        return decoded

    @staticmethod
    def _aad(ref: str, descriptor: ProtectedContentDescriptor, key_id: str) -> bytes:
        return protected_canonical_json({
            "artifact_id": ref,
            "descriptor": descriptor.model_dump(mode="json"),
            "key_id": key_id,
        })

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _authorize(self, descriptor: ProtectedContentDescriptor, assertion: AuthorizationAssertion, action: str) -> None:
        if not assertion.permits(descriptor, action, descriptor.purpose):
            raise ProtectedArtifactError("protected artifact unavailable")

    def _fingerprint(self, descriptor: ProtectedContentDescriptor, content: dict[str, Any]) -> str:
        scoped = {
            "tenant_id": descriptor.tenant_id,
            "owner_principal_id": descriptor.owner_principal_id,
            "purpose": descriptor.purpose,
            "artifact_kind": descriptor.artifact_kind,
            "schema_version": descriptor.schema_version,
            "profile_version": descriptor.profile_version,
            "content": content,
        }
        return hmac.digest(
            self._keys.index_key(descriptor.tenant_id),
            protected_canonical_json(scoped), "sha256",
        ).hex()

    def _envelope(self, ref: str, descriptor: ProtectedContentDescriptor, content: dict[str, Any]) -> dict[str, str]:
        key_id, kek = self._keys.active()
        if not _KEY_ID.fullmatch(key_id) or len(kek) != 32:
            raise ValueError("invalid active protected key")
        dek, payload_nonce, wrap_nonce = AESGCM.generate_key(256), os.urandom(12), os.urandom(12)
        aad = self._aad(ref, descriptor, key_id)
        return {"v": "1", "key_id": key_id, "payload_nonce": self._encode(payload_nonce),
            "ciphertext": self._encode(AESGCM(dek).encrypt(payload_nonce, protected_canonical_json(content), aad)),
            "wrap_nonce": self._encode(wrap_nonce), "wrapped_dek": self._encode(AESGCM(kek).encrypt(wrap_nonce, dek, aad))}

    def _decrypt(self, ref: str, descriptor: ProtectedContentDescriptor, raw: str) -> dict[str, Any]:
        envelope = json.loads(raw)
        if not isinstance(envelope, dict) or set(envelope) != _FIELDS or envelope.get("v") != "1":
            raise ValueError("invalid envelope")
        key_id = envelope["key_id"]
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ValueError("invalid envelope")
        aad = self._aad(ref, descriptor, key_id)
        dek = AESGCM(self._keys.resolve(key_id)).decrypt(
            self._decode(envelope["wrap_nonce"], exact=12), self._decode(envelope["wrapped_dek"], minimum=48), aad)
        if len(dek) != 32:
            raise ValueError("invalid envelope")
        result = json.loads(AESGCM(dek).decrypt(
            self._decode(envelope["payload_nonce"], exact=12), self._decode(envelope["ciphertext"], minimum=16), aad))
        if not isinstance(result, dict):
            raise ValueError("invalid payload")
        return result

    def create_or_match(self, descriptor: ProtectedContentDescriptor, content: dict[str, Any], assertion: AuthorizationAssertion) -> tuple[str, ProtectedArtifactRef]:
        self._authorize(descriptor, assertion, "create")
        fingerprint, ref = self._fingerprint(descriptor, content), new_artifact_ref()
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT ref,descriptor,tombstoned FROM protected_artifacts WHERE fingerprint=?", (fingerprint,)).fetchone()
            if row:
                existing = ProtectedContentDescriptor.model_validate_json(row[1])
                self._authorize(existing, assertion, "create")
                if existing != descriptor or row[2]:
                    conn.execute("ROLLBACK")
                    raise ProtectedArtifactError("protected artifact unavailable")
                conn.execute("COMMIT")
                return "matched", ProtectedArtifactRef(
                    artifact_ref=row[0], fingerprint=fingerprint, descriptor=existing,
                )
            envelope = json.dumps(self._envelope(ref, descriptor, content), separators=(",", ":"))
            conn.execute("INSERT INTO protected_artifacts VALUES(?,?,?,?,0,?)", (ref, fingerprint, descriptor.model_dump_json(), envelope, self._now().isoformat()))
            conn.execute("COMMIT")
        return "created", ProtectedArtifactRef(artifact_ref=ref, fingerprint=fingerprint, descriptor=descriptor)

    def _row(self, ref: ProtectedArtifactRef) -> tuple[ProtectedContentDescriptor, str]:
        with self._conn() as conn:
            row = conn.execute("SELECT descriptor,envelope,tombstoned FROM protected_artifacts WHERE ref=? AND fingerprint=?", (ref.artifact_ref, ref.fingerprint)).fetchone()
        try:
            if not row or row[2]: raise ValueError("missing")
            descriptor = ProtectedContentDescriptor.model_validate_json(row[0])
            if descriptor != ref.descriptor: raise ValueError("descriptor mismatch")
            if descriptor.retention_until and descriptor.retention_until < self._now(): raise ValueError("expired")
            return descriptor, row[1]
        except Exception as exc:
            raise ProtectedArtifactError("protected artifact unavailable") from exc

    def materialize(self, ref: ProtectedArtifactRef, assertion: AuthorizationAssertion) -> dict[str, Any]:
        descriptor, raw = self._row(ref); self._authorize(descriptor, assertion, "materialize")
        try: return self._decrypt(ref.artifact_ref, descriptor, raw)
        except Exception as exc: raise ProtectedArtifactError("protected artifact unavailable") from exc

    def project(self, ref: ProtectedArtifactRef, assertion: AuthorizationAssertion) -> ProtectedContentProjection:
        descriptor, _ = self._row(ref); self._authorize(descriptor, assertion, "project")
        values: dict[str, str | int | bool | None] = {"artifact_kind": descriptor.artifact_kind, "classification": descriptor.classification, "purpose": descriptor.purpose}
        if descriptor.projection_profile == "email-summary":
            values["recipient_count"] = len(self.materialize(ref, assertion.model_copy(update={"action": "materialize"})).get("recipients", []))
        return ProtectedContentProjection(artifact_ref=ref.artifact_ref, fingerprint=ref.fingerprint, values=values)

    def search(self, descriptor: ProtectedContentDescriptor, assertion: AuthorizationAssertion, limit: int = 20) -> list[ProtectedContentProjection]:
        self._authorize(descriptor, assertion, "search")
        if not 1 <= limit <= 100: raise ProtectedArtifactError("protected artifact unavailable")
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ref,fingerprint,descriptor FROM protected_artifacts "
                "WHERE tombstoned=0 AND descriptor=? ORDER BY created_at DESC LIMIT ?",
                (descriptor.model_dump_json(), limit),
            ).fetchall()
        refs = [ProtectedArtifactRef(artifact_ref=row[0], fingerprint=row[1], descriptor=ProtectedContentDescriptor.model_validate_json(row[2])) for row in rows]
        projection = assertion.model_copy(update={"action": "project"})
        return [self.project(ref, projection) for ref in refs]

    def tombstone(self, ref: ProtectedArtifactRef, assertion: AuthorizationAssertion) -> None:
        descriptor, _ = self._row(ref); self._authorize(descriptor, assertion, "tombstone")
        with self._conn() as conn: conn.execute("UPDATE protected_artifacts SET tombstoned=1 WHERE ref=? AND fingerprint=?", (ref.artifact_ref, ref.fingerprint))

    def rekey(self, ref: ProtectedArtifactRef, assertion: AuthorizationAssertion) -> None:
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT descriptor,envelope,tombstoned FROM protected_artifacts WHERE ref=? AND fingerprint=?", (ref.artifact_ref, ref.fingerprint)).fetchone()
            try:
                if not row or row[2]: raise ValueError("missing")
                descriptor = ProtectedContentDescriptor.model_validate_json(row[0]); self._authorize(descriptor, assertion, "rekey")
                data = self._decrypt(ref.artifact_ref, descriptor, row[1])
                envelope = json.dumps(self._envelope(ref.artifact_ref, descriptor, data), separators=(",", ":"))
                updated = conn.execute("UPDATE protected_artifacts SET envelope=? WHERE ref=? AND fingerprint=? AND tombstoned=0 AND envelope=?", (envelope, ref.artifact_ref, ref.fingerprint, row[1]))
                if updated.rowcount != 1: raise ValueError("stale")
                conn.execute("COMMIT")
            except Exception as exc:
                conn.execute("ROLLBACK")
                if isinstance(exc, ProtectedArtifactError): raise
                raise ProtectedArtifactError("protected artifact unavailable") from exc
