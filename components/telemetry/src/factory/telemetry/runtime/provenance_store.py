"""SQLite-backed durable provenance storage with atomic replay claims."""
from __future__ import annotations
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from threading import RLock
from time import sleep
from typing import Iterator, Protocol
from .provenance_models import (
    MappingActivationRecord, TelemetryIdempotencyRecord, TelemetryStoredRecord,
)

class ProvenanceStoreCorruption(RuntimeError):
    """Persisted provenance cannot be parsed safely and is rejected."""

@dataclass(frozen=True)
class AtomicIngestResult:
    existing_batch: TelemetryIdempotencyRecord | None
    existing_sources: dict[str, TelemetryIdempotencyRecord]

class ProvenanceStore(Protocol):
    def atomic_ingest(self, batch_record: TelemetryIdempotencyRecord, source_records: list[tuple[TelemetryIdempotencyRecord, TelemetryStoredRecord | None]]) -> AtomicIngestResult: ...
    def has_materialization_completion(self, telemetry_ref: str, mapping_id: str, mapping_version: str, fanout_index: int) -> bool: ...
    def mark_materialization_completion(self, telemetry_ref: str, mapping_id: str, mapping_version: str, fanout_index: int) -> None: ...
    def get_idempotency(self, tenant_id: str, producer_id: str, key_kind: str, key: str) -> TelemetryIdempotencyRecord | None: ...
    def put_idempotency(self, record: TelemetryIdempotencyRecord) -> None: ...
    def get_record(self, telemetry_ref: str) -> TelemetryStoredRecord | None: ...
    def put_record(self, record: TelemetryStoredRecord) -> None: ...
    def claim_materialization(self, telemetry_ref: str) -> bool: ...
    def complete_materialization(self, telemetry_ref: str) -> bool: ...
    def release_materialization(self, telemetry_ref: str) -> None: ...
    def mark_materialized(self, telemetry_ref: str) -> None: ...
    def get_activation(self) -> MappingActivationRecord | None: ...
    def put_activation(self, record: MappingActivationRecord) -> None: ...

from .provenance_store_completion import (
    MaterializationCompletionStoreMixin, initialize_materialization_completions,
)

class JsonProvenanceStore(MaterializationCompletionStoreMixin):
    """Compatibility-named SQLite store; ``path=None`` is isolated in-memory."""
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self._path is None else None
        self._initialize()
    @contextmanager
    def _connection(self, transaction: bool = False) -> Iterator[sqlite3.Connection]:
        lock = self._lock if self._memory is not None else nullcontext()
        with lock:
            conn = self._memory or sqlite3.connect(str(self._path), timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            try:
                if transaction:
                    conn.execute("BEGIN IMMEDIATE")
                yield conn
                if transaction:
                    conn.commit()
            except Exception:
                if transaction:
                    conn.rollback()
                raise
            finally:
                if conn is not self._memory:
                    conn.close()
    def _initialize(self) -> None:
        for attempt in range(8):
            try:
                with self._connection() as conn:
                    conn.execute("PRAGMA busy_timeout=30000")
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=FULL")
                    conn.executescript("""
                    CREATE TABLE IF NOT EXISTS idempotency (
                        tenant_id TEXT NOT NULL, producer_id TEXT NOT NULL,
                        key_kind TEXT NOT NULL, key TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, producer_id, key_kind, key)
                    );
                    CREATE TABLE IF NOT EXISTS records (
                        telemetry_ref TEXT PRIMARY KEY, record_json TEXT NOT NULL,
                        materialized INTEGER NOT NULL DEFAULT 0,
                        materializing INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS activation (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        record_json TEXT NOT NULL
                    );
                """)
                    initialize_materialization_completions(conn)
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 7:
                    raise
                sleep(0.05 * (2**attempt))
    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    @staticmethod
    def _idempotency(row: sqlite3.Row | None) -> TelemetryIdempotencyRecord | None:
        if row is None:
            return None
        try:
            return TelemetryIdempotencyRecord.model_validate_json(row["record_json"])
        except (TypeError, ValueError) as exc:
            raise ProvenanceStoreCorruption("invalid idempotency record") from exc
    def _get_idempotency(self, conn: sqlite3.Connection, tenant: str, producer: str, kind: str, key: str) -> TelemetryIdempotencyRecord | None:
        row = conn.execute("SELECT record_json FROM idempotency WHERE tenant_id=? AND producer_id=? AND key_kind=? AND key=?", (tenant, producer, kind, key)).fetchone()
        return self._idempotency(row)
    def get_idempotency(self, tenant_id: str, producer_id: str, key_kind: str, key: str) -> TelemetryIdempotencyRecord | None:
        with self._connection() as conn:
            return self._get_idempotency(conn, tenant_id, producer_id, key_kind, key)
    def put_idempotency(self, record: TelemetryIdempotencyRecord) -> None:
        with self._connection(transaction=True) as conn:
            conn.execute("INSERT OR REPLACE INTO idempotency VALUES (?,?,?,?,?)", (record.tenant_id, record.producer_id, record.key_kind, record.key, record.model_dump_json()))
    def atomic_ingest(self, batch_record: TelemetryIdempotencyRecord, source_records: list[tuple[TelemetryIdempotencyRecord, TelemetryStoredRecord | None]]) -> AtomicIngestResult:
        with self._connection(transaction=True) as conn:
            existing_batch = self._get_idempotency(conn, batch_record.tenant_id, batch_record.producer_id, "batch", batch_record.key)
            if existing_batch is not None:
                return AtomicIngestResult(existing_batch, {})
            existing_sources: dict[str, TelemetryIdempotencyRecord] = {}
            for source_record, stored in source_records:
                prior = self._get_idempotency(conn, source_record.tenant_id, source_record.producer_id, "source", source_record.key)
                if prior is not None:
                    existing_sources[source_record.key] = prior
                    continue
                if stored is not None:
                    conn.execute("INSERT INTO records VALUES (?,?,0,0)", (stored.telemetry_ref, stored.model_dump_json()))
                conn.execute("INSERT INTO idempotency VALUES (?,?,?,?,?)", (source_record.tenant_id, source_record.producer_id, "source", source_record.key, source_record.model_dump_json()))
            conn.execute("INSERT INTO idempotency VALUES (?,?,?,?,?)", (batch_record.tenant_id, batch_record.producer_id, "batch", batch_record.key, batch_record.model_dump_json()))
            return AtomicIngestResult(None, existing_sources)
    def get_record(self, telemetry_ref: str) -> TelemetryStoredRecord | None:
        with self._connection() as conn:
            row = conn.execute("SELECT record_json, materialized FROM records WHERE telemetry_ref=?", (telemetry_ref,)).fetchone()
        if row is None:
            return None
        try:
            record = TelemetryStoredRecord.model_validate_json(row["record_json"])
        except (TypeError, ValueError) as exc:
            raise ProvenanceStoreCorruption("invalid telemetry record") from exc
        return record.model_copy(update={"materialized": bool(row["materialized"])})
    def put_record(self, record: TelemetryStoredRecord) -> None:
        with self._connection(transaction=True) as conn:
            conn.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,0)", (record.telemetry_ref, record.model_dump_json(), int(record.materialized)))
    def claim_materialization(self, telemetry_ref: str) -> bool:
        with self._connection(transaction=True) as conn:
            row = conn.execute("UPDATE records SET materializing=1 WHERE telemetry_ref=? AND materialized=0 AND materializing=0", (telemetry_ref,))
            return row.rowcount == 1
    def complete_materialization(self, telemetry_ref: str) -> bool:
        with self._connection(transaction=True) as conn:
            row = conn.execute("UPDATE records SET materialized=1, materializing=0 WHERE telemetry_ref=? AND materializing=1", (telemetry_ref,))
            return row.rowcount == 1
    def release_materialization(self, telemetry_ref: str) -> None:
        with self._connection(transaction=True) as conn:
            conn.execute("UPDATE records SET materializing=0 WHERE telemetry_ref=? AND materialized=0", (telemetry_ref,))
    def mark_materialized(self, telemetry_ref: str) -> None:
        with self._connection(transaction=True) as conn:
            conn.execute("UPDATE records SET materialized=1, materializing=0 WHERE telemetry_ref=?", (telemetry_ref,))
    def get_activation(self) -> MappingActivationRecord | None:
        with self._connection() as conn:
            row = conn.execute("SELECT record_json FROM activation WHERE singleton=1").fetchone()
        if row is None:
            return None
        try:
            return MappingActivationRecord.model_validate_json(row["record_json"])
        except (TypeError, ValueError) as exc:
            raise ProvenanceStoreCorruption("invalid mapping activation") from exc
    def put_activation(self, record: MappingActivationRecord) -> None:
        with self._connection(transaction=True) as conn:
            conn.execute("INSERT OR REPLACE INTO activation VALUES (1,?)", (record.model_dump_json(),))

SQLiteProvenanceStore = JsonProvenanceStore
__all__ = ["AtomicIngestResult", "JsonProvenanceStore", "ProvenanceStore", "ProvenanceStoreCorruption", "SQLiteProvenanceStore"]
