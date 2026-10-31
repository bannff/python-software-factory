"""Durably record named-step failures that occur before an attempt is claimed."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    is_protected_payload, protected_error_text, validate_protected_persistence,
)
from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.models import RunRecord, StepDefinition
from factory.workflow.runtime.task_ids import step_execution_id


def record(
    connect: Any, *, run: RunRecord, step: StepDefinition,
    inputs: dict[str, Any], error: str, protected: bool = False,
) -> None:
    protected = protected or is_protected_payload(inputs)
    validate_protected_persistence(inputs, protected=protected)
    error = protected_error_text(error, protected=protected)
    if not run.run_execution_id or not run.workflow_version_id:
        raise ValueError("run is not bound to a durable workflow snapshot")
    execution_id = step_execution_id(run.run_execution_id, step.id)
    input_json = canonical_json(inputs)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO step_executions"
            "(step_execution_id,run_id,workflow_version_id,step_id,status,input_json,error) "
            "VALUES(?,?,?,?,'failed',?,?)",
            (execution_id, run.run_id, run.workflow_version_id,
             step.id, input_json, error),
        )
        conn.execute(
            "UPDATE step_executions SET status='failed',error=? "
            "WHERE step_execution_id=? AND status NOT IN ('succeeded','cancelled')",
            (error, execution_id),
        )
