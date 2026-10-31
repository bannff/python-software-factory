"""Validate authoritative durable step material before projection."""
from __future__ import annotations

from typing import Any

from factory.workflow.runtime.attempt_binding import verify_attempt_binding
from factory.workflow.runtime.canonical import canonical_json, canonical_loads
from factory.workflow.runtime.models import RunRecord, ToolTarget
from factory.workflow.runtime.run_binding import DurableAttemptBindingError
from factory.workflow.runtime.task_ids import step_execution_id
from factory.workflow.runtime.task_models import VerifiedStepResult
from factory.workflow.runtime.task_refs import digest_json


def load_verified(
    connect: Any, *, run: RunRecord, step_id: str, expected_target: ToolTarget,
    expected_step_input: str, idempotency_argument: str | None,
) -> VerifiedStepResult:
    """Return output/evidence only when every attempt binding is authoritative."""
    if not run.run_execution_id or not run.workflow_version_id:
        raise ValueError("run is not bound to a durable workflow snapshot")
    expected_id = step_execution_id(run.run_execution_id, step_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT s.step_execution_id,s.run_id,s.workflow_version_id,s.step_id,"
            "s.status AS step_status,s.input_json AS step_input,"
            "s.output_json,s.output_digest,s.artifact_refs_json,s.evidence_json,"
            "a.attempt_id,a.attempt_number,a.status AS attempt_status,"
            "a.input_json AS attempt_input,a.output_json AS attempt_output,"
            "a.output_digest AS attempt_digest,a.envelope_json,a.envelope_digest,"
            "a.evidence_digest,a.evidence_json AS attempt_evidence "
            "FROM step_executions s JOIN task_attempts a USING(step_execution_id) "
            "WHERE s.step_execution_id=? ORDER BY a.attempt_number",
            (expected_id,),
        ).fetchall()
    if not rows:
        raise ValueError(f"unresolved workflow step output: {step_id}")
    row = rows[-1]
    if row["step_execution_id"] != expected_id or row["run_id"] != run.run_id \
            or row["workflow_version_id"] != run.workflow_version_id \
            or row["step_id"] != step_id:
        raise DurableAttemptBindingError("workflow step output binding mismatch")
    if row["step_input"] != expected_step_input:
        raise DurableAttemptBindingError(
            "workflow step input does not match frozen projected arguments"
        )
    for expected_number, attempt in enumerate(rows, start=1):
        verify_attempt_binding(
            step_execution_id=expected_id,
            attempt_number=attempt["attempt_number"],
            attempt_id=attempt["attempt_id"],
            attempt_input_json=attempt["attempt_input"],
            step_input_json=attempt["step_input"],
            idempotency_argument=idempotency_argument,
            expected_number=expected_number,
        )
    if row["step_status"] != "succeeded" \
            or row["attempt_status"] != "succeeded" \
            or row["output_json"] is None:
        raise ValueError(f"unresolved workflow step output: {step_id}")
    output = canonical_loads(row["output_json"])
    evidence = canonical_loads(row["evidence_json"])
    artifacts = output.get("artifacts", {}) if isinstance(output, dict) else {}
    if canonical_json(output) != row["output_json"] \
            or digest_json(output) != row["output_digest"]:
        raise ValueError("workflow step output integrity mismatch")
    if row["attempt_output"] != row["output_json"] \
            or row["attempt_digest"] != row["output_digest"]:
        raise ValueError("workflow attempt output integrity mismatch")
    if row["attempt_evidence"] != row["evidence_json"] \
            or evidence.get("output_sha256") != row["output_digest"]:
        raise ValueError("workflow step evidence integrity mismatch")
    envelope = canonical_loads(row["envelope_json"])
    if canonical_json(evidence) != row["evidence_json"] \
            or canonical_json(envelope) != row["envelope_json"]:
        raise ValueError("workflow attempt evidence is not canonical")
    if row["envelope_digest"] != digest_json(envelope) \
            or row["evidence_digest"] != digest_json(evidence):
        raise ValueError("workflow attempt evidence digest mismatch")
    gateway = evidence.get("gateway", {})
    if gateway.get("target") != expected_target.model_dump(mode="json") \
            or gateway.get("attempt_id") != row["attempt_id"] \
            or gateway.get("transport_envelope_sha256") != digest_json(envelope):
        raise ValueError("workflow step provenance mismatch")
    if row["artifact_refs_json"] != canonical_json(artifacts):
        raise ValueError("workflow step artifact reference mismatch")
    return VerifiedStepResult(
        attempt_id=row["attempt_id"], attempt_number=row["attempt_number"],
        output=output, evidence=evidence,
    )


def load_output(
    connect: Any, *, run: RunRecord, step_id: str, expected_target: ToolTarget,
    expected_step_input: str, idempotency_argument: str | None,
) -> Any:
    """Compatibility wrapper for existing output-only callers."""
    return load_verified(
        connect, run=run, step_id=step_id, expected_target=expected_target,
        expected_step_input=expected_step_input,
        idempotency_argument=idempotency_argument,
    ).output
