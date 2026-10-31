"""Transactional generic execution-event journal with legacy read parity."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from factory.mcp_utils.interface import (
    is_protected_payload, protected_error_value, telemetry_projection,
    validate_protected_persistence,
)
from factory.workflow.runtime.bounded import bounded_canonical
from factory.workflow.runtime.canonical import canonical_loads


def _digest(encoded: str) -> str:
    return hashlib.sha256(encoded.encode()).hexdigest()


def append(connect: Any, *, workflow_run_id: str, attempt_id: str, revision: int,
           engine_id: str, registration_digest: str, request_digest: str,
           provider_request_digest: str, sequence: int, terminal: bool,
           raw_evidence: dict[str, Any], safe_metadata: dict[str, str],
           now: datetime) -> dict[str, Any]:
    protected = is_protected_payload(raw_evidence)
    if protected:
        # Native stream events may contain nested text/content. Keep only the
        # allowlisted projection for those events; reject direct business fields
        # at the generic persistence boundary.
        shallow = {key: None for key in raw_evidence}
        try:
            validate_protected_persistence(shallow)
        except ValueError:
            raise
        if "type" in raw_evidence:
            raw_evidence = telemetry_projection(raw_evidence, protected=True)
        else:
            validate_protected_persistence(raw_evidence, protected=True)
    raw_evidence = protected_error_value(raw_evidence, protected=protected)
    validate_protected_persistence(raw_evidence, protected=protected)
    safe_metadata = protected_error_value(safe_metadata, protected=False)
    validate_protected_persistence(safe_metadata, protected=False)
    raw, raw_json = bounded_canonical(raw_evidence)
    metadata, metadata_json = bounded_canonical(safe_metadata)
    if any(type(key) is not str or type(value) is not str for key, value in metadata.items()):
        raise ValueError("safe_metadata must be a strict dict[str, str]")
    if (len(metadata) > 16 or any(len(key) > 32 or len(value) > 256
            for key, value in metadata.items())):
        raise ValueError("safe_metadata exceeds bounded key/count/value limits")
    raw_digest = _digest(raw_json)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        owner = conn.execute("SELECT a.status,a.revision,a.input_json,s.run_id,r.status run_status "
            "FROM task_attempts a JOIN step_executions s USING(step_execution_id) "
            "JOIN runs r ON r.run_id=s.run_id WHERE a.attempt_id=?", (attempt_id,)).fetchone()
        material = canonical_loads(owner["input_json"]) if owner else None
        exact = owner is not None and owner["run_id"] == workflow_run_id and owner["revision"] == revision and isinstance(material, dict) and all(material.get(key) == value for key, value in {
            "engine_id": engine_id, "registration_digest": registration_digest,
            "request_digest": request_digest, "provider_request_digest": provider_request_digest,
        }.items())
        if not exact or owner["status"] != "running" or owner["run_status"] not in {"pending", "running", "waiting"}:
            raise ValueError("execution event owner is stale or terminal")
        old = conn.execute("SELECT * FROM execution_events WHERE attempt_id=? AND revision=? AND sequence=?", (attempt_id, revision, sequence)).fetchone()
        if old:
            same = all(old[key] == value for key, value in {
                "run_id": workflow_run_id, "engine_id": engine_id, "registration_digest": registration_digest,
                "request_digest": request_digest, "provider_request_digest": provider_request_digest,
                "raw_digest": raw_digest, "raw_json": raw_json, "safe_metadata_json": metadata_json,
            }.items()) and bool(old["terminal"]) is terminal
            if not same: raise ValueError("execution event sequence conflict")
            return {"appended": False, "raw_digest": raw_digest}
        last = conn.execute("SELECT sequence,terminal FROM execution_events WHERE attempt_id=? AND revision=? ORDER BY sequence DESC LIMIT 1", (attempt_id, revision)).fetchone()
        if last and bool(last["terminal"]): raise ValueError("execution event follows terminal")
        if sequence != (0 if last is None else int(last["sequence"]) + 1):
            raise ValueError("execution event sequence is not contiguous")
        conn.execute("INSERT INTO execution_events(attempt_id,revision,sequence,run_id,engine_id,registration_digest,request_digest,provider_request_digest,raw_digest,terminal,raw_json,safe_metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (attempt_id, revision, sequence, workflow_run_id, engine_id, registration_digest, request_digest, provider_request_digest, raw_digest, int(terminal), raw_json, metadata_json, now.isoformat()))
    return {"appended": True, "raw_digest": raw_digest}


def get(connect: Any, *, workflow_run_id: str, attempt_id: str | None, revision: int | None) -> list[dict[str, Any]]:
    clauses, values = ["run_id=?"], [workflow_run_id]
    for name, value in (("attempt_id", attempt_id), ("revision", revision)):
        if value is not None: clauses.append(f"{name}=?"); values.append(value)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM execution_events WHERE " + " AND ".join(clauses) + " ORDER BY created_at,attempt_id,revision,sequence", values).fetchall()
    return [{**dict(row), "terminal": bool(row["terminal"]), "raw_evidence": canonical_loads(row["raw_json"]), "safe_metadata": canonical_loads(row["safe_metadata_json"])} for row in rows]


__all__ = ["append", "get"]
