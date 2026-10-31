"""Durably seal one progressive named-MCP attempt for continuation."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    is_protected_payload, protected_error_value, validate_protected_persistence,
)
from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.task_refs import digest_json


def record(
    connect: Any, *, attempt_id: str, revision: int, lease_token: str,
    output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
    protected: bool = False,
) -> bool:
    """Seal an attempt as continued and return whether this call won the CAS."""
    flags = tuple(protected or is_protected_payload(value)
                  for value in (output, envelope, evidence))
    safe = tuple(protected_error_value(value, protected=flag)
                 for value, flag in zip((output, envelope, evidence), flags))
    for value, flag in zip(safe, flags):
        validate_protected_persistence(value, protected=flag)
    output_json, envelope_json, evidence_json = map(canonical_json, safe)
    digests = tuple(digest_json(value) for value in safe)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT a.*,s.run_id FROM task_attempts a JOIN step_executions s "
            "USING(step_execution_id) WHERE attempt_id=?", (attempt_id,),
        ).fetchone()
        if row is None:
            raise ValueError("task attempt missing")
        if row["status"] == "continued":
            if row["lease_token"] != lease_token or row["revision"] != revision:
                raise ValueError("stale task continuation")
            if (row["output_json"], row["envelope_json"], row["evidence_json"]) \
                    != (output_json, envelope_json, evidence_json):
                raise ValueError("durable continuation conflict")
            return False
        active = conn.execute(
            "SELECT status FROM runs WHERE run_id=?", (row["run_id"],),
        ).fetchone()
        if active is None or active["status"] in {"cancelled", "failed", "succeeded"}:
            raise ValueError("stale task continuation")
        updated = conn.execute(
            "UPDATE task_attempts SET status='continued',output_json=?,"
            "envelope_json=?,evidence_json=?,output_digest=?,envelope_digest=?,"
            "evidence_digest=?,lease_expires_at=NULL WHERE attempt_id=? "
            "AND status='running' AND lease_token=? AND revision=?",
            (output_json, envelope_json, evidence_json, *digests,
             attempt_id, lease_token, revision),
        )
        if updated.rowcount != 1:
            raise ValueError("stale task continuation")
        conn.execute(
            "UPDATE step_executions SET status='pending',error=NULL "
            "WHERE step_execution_id=?", (row["step_execution_id"],),
        )
    return True


__all__ = ["record"]
