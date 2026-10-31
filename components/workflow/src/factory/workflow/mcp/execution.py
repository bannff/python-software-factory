"""Private, provider-neutral Workflow execution handoffs."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from factory.mcp_utils.interface import ToolResult, ok, operational, service_only
from ..runtime.envelope import parse_envelope
from .contracts.base import json_safe
from .contracts.operational import (
    AppendExecutionEventInput, AppendExecutionEventOutput, EnrollExecutionInput,
    ExecutionRunOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: WorkflowRuntime) -> None:
    """Trusted in-process composition only; gateway claims enforce callers."""
    @mcp.tool(name="workflow.enroll_execution")
    @service_only(callers={"agent", "migration"}, binding="enrollment")
    @operational(input_model=EnrollExecutionInput, output_model=ExecutionRunOutput)
    def enroll_execution(engine_id: str, request: dict, provider_request_digest: str,
                         manifest_digest: str, run_key: str,
                         launch_metadata: dict[str, str] | None = None,
                         execute: bool = True,
                         envelope: dict | None = None) -> ToolResult[ExecutionRunOutput]:
        if manifest_digest != provider_request_digest:
            raise ValueError("manifest_digest must match provider_request_digest")
        result = runtime.enroll_execution(engine_id=engine_id, request=request,
            provider_request_digest=provider_request_digest, run_key=run_key,
            envelope=parse_envelope(envelope), execute=execute,
            launch_metadata=launch_metadata or {})
        return ok(ExecutionRunOutput.model_validate(json_safe(result)))

    @mcp.tool(name="workflow.append_execution_event")
    @service_only(callers={"agent"}, binding="execution")
    @operational(input_model=AppendExecutionEventInput,
                 output_model=AppendExecutionEventOutput, idempotent=False)
    def append_execution_event(workflow_run_id: str, attempt_id: str, revision: int,
        engine_id: str, registration_digest: str, request_digest: str,
        provider_request_digest: str, sequence: int, terminal: bool,
        raw_evidence: dict, safe_metadata: dict[str, str] | None = None,
    ) -> ToolResult[AppendExecutionEventOutput]:
        result = runtime.append_execution_event(
            workflow_run_id=workflow_run_id, attempt_id=attempt_id, revision=revision,
            engine_id=engine_id, registration_digest=registration_digest,
            request_digest=request_digest, provider_request_digest=provider_request_digest,
            sequence=sequence, terminal=terminal, raw_evidence=raw_evidence,
            safe_metadata=safe_metadata or {},
        )
        return ok(AppendExecutionEventOutput(appended=bool(result["appended"]),
            sequence=sequence, raw_digest=str(result["raw_digest"])))


__all__ = ["register"]
