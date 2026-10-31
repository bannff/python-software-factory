"""Security and cross-connection tests for Telemetry provenance."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext, TelemetryIngestBatch, TelemetryIngestItem,
)
from factory.telemetry.runtime.provenance_policy import RetentionPolicy
from factory.telemetry.runtime.provenance_runtime import TelemetryProvenanceRuntime
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore


def _context() -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id="tenant", producer_id="producer", principal_id="principal",
        visibility="private", source_namespace="security-tests",
    )


def _batch(value: dict, source_id: str = "source") -> TelemetryIngestBatch:
    return TelemetryIngestBatch(
        batch_id="batch", items=[TelemetryIngestItem(
            source_id=source_id, canonical_payload=value, signal="span",
            attributes={"secret": "attribute-secret", "safe": "ok"},
        )],
    )


def test_server_policy_redacts_before_retention_and_records_evidence() -> None:
    policy = RetentionPolicy(version="redact-v1", redact_fields=frozenset({"secret"}))
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore(), policy=policy)
    result = runtime.ingest(_batch({"secret": "payload-secret", "safe": "ok"}), _context())
    reference = result.outcomes[0].telemetry_ref

    assert result.status == "accepted"
    assert result.outcomes[0].policy_version == "redact-v1"
    record = runtime.store.get_record(reference)
    assert record is not None
    assert record.item.canonical_payload == {"secret": "[REDACTED]", "safe": "ok"}
    assert record.item.attributes == {"secret": "[REDACTED]", "safe": "ok"}
    assert record.policy_version == "redact-v1"
    assert record.policy_outcome == "redacted"
    assert record.policy_evidence["outcome"] == "redacted"
    idem = runtime.store.get_idempotency("tenant", "producer", "source", "source")
    assert idem is not None
    assert idem.policy_version == "redact-v1"
    assert idem.policy_evidence["redacted_fields"] == ["secret"]


def test_sampling_is_server_owned_and_durable() -> None:
    policy = RetentionPolicy(version="sample-v1", sample_rate=0.0)
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore(), policy=policy)
    result = runtime.ingest(_batch({"safe": "value"}), _context())

    assert result.status == "accepted"
    assert result.outcomes[0].status == "sampled_out"
    assert result.outcomes[0].telemetry_ref is None
    assert runtime.store.get_record("telemetry:missing") is None
    idem = runtime.store.get_idempotency("tenant", "producer", "source", "source")
    assert idem is not None
    assert idem.policy_outcome == "sampled_out"
    assert idem.outcome_ref.startswith("sampled:telemetry:")


def _ingest_in_separate_store(path: str) -> str:
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore(path))
    return runtime.ingest(_batch({"value": 1}), _context()).status


def test_separate_durable_connections_accept_one_replay(tmp_path: Path) -> None:
    path = str(tmp_path / "provenance.sqlite3")
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(_ingest_in_separate_store, [path, path]))

    assert sorted(statuses) == ["accepted", "duplicate"]
    restored = TelemetryProvenanceRuntime(JsonProvenanceStore(path))
    assert restored.store.get_idempotency("tenant", "producer", "batch", "batch") is not None


def test_materialization_claim_is_atomic_across_connections(tmp_path: Path) -> None:
    path = tmp_path / "provenance.sqlite3"
    runtime = TelemetryProvenanceRuntime(JsonProvenanceStore(path))
    result = runtime.ingest(_batch({"value": 1}), _context())
    reference = result.outcomes[0].telemetry_ref
    stores = [JsonProvenanceStore(path), JsonProvenanceStore(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda store: store.claim_materialization(reference), stores))

    assert sorted(claims) == [False, True]
    winner = stores[claims.index(True)]
    assert winner.complete_materialization(reference) is True
    assert winner.get_record(reference).materialized is True


def test_corrupt_durable_store_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provenance.sqlite3"
    path.write_text("not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        JsonProvenanceStore(path)
