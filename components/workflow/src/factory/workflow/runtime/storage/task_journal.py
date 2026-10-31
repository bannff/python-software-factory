"""Transactional completion and failure journal for named-MCP attempts."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    is_protected_payload, protected_error_text, protected_error_value,
    validate_protected_persistence,
)
from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.task_refs import digest_json
from factory.workflow.runtime.task_models import CancelledAttempt


def complete(
    connect: Any, *, attempt_id: str, revision: int, lease_token: str,
    output: Any, envelope: dict[str, Any], evidence: dict[str, Any],
    protected: bool = False,
) -> bool:
    protected_output = protected or is_protected_payload(output)
    protected_evidence = protected or is_protected_payload(evidence)
    protected_envelope = protected or is_protected_payload(envelope)
    if protected_output:
        validate_protected_persistence(output, protected=True)
    if protected_evidence:
        validate_protected_persistence(evidence, protected=True)
    safe_output = protected_error_value(output, protected=protected_output)
    safe_envelope = protected_error_value(envelope, protected=protected_envelope)
    safe_evidence = protected_error_value(evidence, protected=protected_evidence)
    for value, value_protected in (
        (safe_output, protected_output),
        (safe_envelope, protected_envelope),
        (safe_evidence, protected_evidence),
    ):
        validate_protected_persistence(value, protected=value_protected)
    output_json, envelope_json, evidence_json = map(
        canonical_json, (safe_output, safe_envelope, safe_evidence),
    )
    digests = (digest_json(safe_output), digest_json(safe_envelope), digest_json(safe_evidence))
    artifacts = safe_output.get("artifacts", {}) if isinstance(safe_output, dict) else {}
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT a.*,s.run_id FROM task_attempts a JOIN step_executions s "
            "USING(step_execution_id) WHERE attempt_id=?", (attempt_id,),
        ).fetchone()
        if row is None:
            raise ValueError("task attempt missing")
        if row["status"] == "succeeded":
            if row["lease_token"] != lease_token or row["revision"] != revision:
                raise ValueError("stale task completion")
            if (row["output_json"], row["envelope_json"], row["evidence_json"]) != (
                output_json, envelope_json, evidence_json,
            ):
                raise ValueError("durable completion conflict")
            return False
        active = conn.execute(
            "SELECT status FROM runs WHERE run_id=?", (row["run_id"],),
        ).fetchone()
        if active is None or active["status"] in {"cancelled", "failed", "succeeded"}:
            raise ValueError("stale task completion")
        updated = conn.execute(
            "UPDATE task_attempts SET status='succeeded',output_json=?,"
            "envelope_json=?,evidence_json=?,output_digest=?,envelope_digest=?,"
            "evidence_digest=?,lease_expires_at=NULL WHERE attempt_id=? "
            "AND status='running' AND lease_token=? AND revision=?",
            (output_json, envelope_json, evidence_json, *digests,
             attempt_id, lease_token, revision),
        )
        if updated.rowcount != 1:
            raise ValueError("stale task completion")
        conn.execute(
            "UPDATE step_executions SET status='succeeded',output_json=?,"
            "output_digest=?,artifact_refs_json=?,evidence_json=?,error=NULL "
            "WHERE step_execution_id=?",
            (output_json, digests[0], canonical_json(artifacts), evidence_json,
             row["step_execution_id"]),
        )
    return True


def fail(
    connect: Any, *, attempt_id: str, revision: int, lease_token: str,
    error: str, envelope: dict[str, Any] | None,
    retryable: bool, max_attempts: int, protected: bool = False,
) -> bool:
    protected = protected or is_protected_payload(envelope)
    error = protected_error_text(error, protected=protected)
    safe_envelope = (
        protected_error_value(envelope, protected=protected)
        if envelope is not None else None
    )
    if safe_envelope is not None:
        validate_protected_persistence(safe_envelope, protected=protected)
    envelope_json = canonical_json(safe_envelope) if safe_envelope is not None else None
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM task_attempts WHERE attempt_id=?", (attempt_id,),
        ).fetchone()
        if row is None:
            raise ValueError("task attempt missing")
        if row["status"] == "failed":
            if row["lease_token"] != lease_token or row["revision"] != revision:
                raise ValueError("stale task failure")
            if row["error"] != error or row["envelope_json"] != envelope_json:
                raise ValueError("durable failure conflict")
            return bool(row["retry_approved"])
        prior_failures = conn.execute(
            "SELECT COUNT(*) FROM task_attempts WHERE step_execution_id=? "
            "AND status='failed'", (row["step_execution_id"],),
        ).fetchone()[0]
        approved = int(retryable and prior_failures + 1 < max_attempts)
        updated = conn.execute(
            "UPDATE task_attempts SET status='failed',error=?,envelope_json=?,"
            "retry_approved=?,lease_expires_at=NULL WHERE attempt_id=? "
            "AND status='running' AND lease_token=? AND revision=?",
            (error, envelope_json, approved, attempt_id, lease_token, revision),
        )
        if updated.rowcount != 1:
            raise ValueError("stale task failure")
        conn.execute(
            "UPDATE step_executions SET status='failed',error=? "
            "WHERE step_execution_id=?", (error, row["step_execution_id"]),
        )
    return bool(approved)


def cancel_attempts(
    connect: Any, *, run_id: str, reason: str,
) -> list[CancelledAttempt]:
    """Fence active attempts and return their exact pre-fence owner records."""
    reason = protected_error_text(reason)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT a.attempt_id,a.revision,a.status,a.input_json,s.run_id "
            "FROM task_attempts a JOIN step_executions s "
            "USING(step_execution_id) WHERE s.run_id=? "
            "AND a.status IN ('pending','running') "
            "ORDER BY s.step_id,a.attempt_number", (run_id,),
        ).fetchall()
        attempts = [CancelledAttempt(
            workflow_run_id=str(row["run_id"]),
            attempt_id=str(row["attempt_id"]), revision=int(row["revision"]),
            status=str(row["status"]), canonical_input=str(row["input_json"]),
        ) for row in rows]
        conn.execute(
            "UPDATE task_attempts SET status='cancelled',error=?,"
            "revision=revision+1,lease_expires_at=NULL WHERE step_execution_id IN "
            "(SELECT step_execution_id FROM step_executions WHERE run_id=?) "
            "AND status IN ('pending','running')", (reason, run_id),
        )
        conn.execute(
            "UPDATE step_executions SET status='cancelled',error=? WHERE run_id=? "
            "AND status IN ('pending','running')", (reason, run_id),
        )
    return attempts


def list_attempts(connect: Any, *, run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT a.* FROM task_attempts a JOIN step_executions s "
            "USING(step_execution_id) WHERE s.run_id=? "
            "ORDER BY s.step_id,a.attempt_number", (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]
