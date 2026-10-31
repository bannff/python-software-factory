"""Typed operational MCP tools for Workflow."""
from __future__ import annotations

from typing import TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational
from typing import Any

from ..runtime.envelope import parse_envelope
from ..runtime.execution.adapters import TaskStatus
from .contracts.base import json_safe
from .contracts.operational import (
    CancelRunInput,
    EmitEventInput,
    ListRunsInput,
    ListRunsOutput,
    ListTasksInput,
    OperationOutput,
    RunIdInput,
    RunOutput,
    StartRunInput,
    StartRunOutput,
    StepOutput,
    TaskOutput,
    TasksOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: WorkflowRuntime) -> None:
    """Register strict operational Workflow tools."""

    @mcp.tool(name="workflow.start_run")
    @operational(input_model=StartRunInput, output_model=StartRunOutput)
    def start_run(
        workflow_name_or_id: str,
        input: dict | None = None,
        run_key: str | None = None,
        envelope: dict | None = None,
    ) -> ToolResult[StartRunOutput]:
        result = runtime.start_run(
            workflow_name_or_id=workflow_name_or_id,
            input=input or {},
            envelope=parse_envelope(envelope),
            run_key=run_key,
        )
        return StartRunOutput.model_validate(json_safe(result))

    @mcp.tool(name="workflow.get_run")
    @operational(input_model=RunIdInput, output_model=RunOutput)
    def get_run(
        run_id: str, envelope: dict | None = None,
    ) -> ToolResult[RunOutput]:
        return RunOutput.model_validate(
            json_safe(runtime.get_run(run_id=run_id, envelope=parse_envelope(envelope)))
        )

    @mcp.tool(name="workflow.list_runs")
    @operational(input_model=ListRunsInput, output_model=ListRunsOutput)
    def list_runs(
        filter: dict | None = None,
        pagination: dict | None = None,
        envelope: dict | None = None,
    ) -> ToolResult[ListRunsOutput]:
        result = runtime.list_runs(
            filter=filter or {},
            pagination=pagination or {},
            envelope=parse_envelope(envelope),
        )
        return ListRunsOutput.model_validate(json_safe(result))

    @mcp.tool(name="workflow.cancel_run")
    @operational(input_model=CancelRunInput, output_model=OperationOutput)
    def cancel_run(
        run_id: str, reason: str | None = None, envelope: dict | None = None,
    ) -> ToolResult[OperationOutput]:
        return OperationOutput.model_validate(
            json_safe(runtime.cancel_run(
                run_id=run_id, reason=reason, envelope=parse_envelope(envelope),
            ))
        )

    @mcp.tool(name="workflow.resume_run")
    @operational(input_model=RunIdInput, output_model=OperationOutput)
    def resume_run(
        run_id: str, envelope: dict | None = None,
    ) -> ToolResult[OperationOutput]:
        return OperationOutput.model_validate(
            json_safe(runtime.resume_run(
                run_id=run_id, envelope=parse_envelope(envelope),
            ))
        )

    @mcp.tool(name="workflow.step_run")
    @operational(input_model=RunIdInput, output_model=StepOutput)
    def step_run(
        run_id: str, envelope: dict | None = None,
    ) -> ToolResult[StepOutput]:
        return StepOutput.model_validate(
            json_safe(runtime.step_run(
                run_id=run_id, envelope=parse_envelope(envelope),
            ))
        )

    @mcp.tool(name="workflow.emit_event")
    @operational(input_model=EmitEventInput, output_model=OperationOutput)
    def emit_event(
        run_id: str,
        event_type: str,
        payload: dict | None = None,
        envelope: dict | None = None,
    ) -> ToolResult[OperationOutput]:
        return OperationOutput.model_validate(
            json_safe(runtime.emit_event(
                run_id=run_id,
                event_type=event_type,
                payload=payload or {},
                envelope=parse_envelope(envelope),
            ))
        )

    @mcp.tool(name="workflow.executor.list_tasks")
    @operational(input_model=ListTasksInput, output_model=TasksOutput)
    def executor_list_tasks(
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 100,
    ) -> ToolResult[TasksOutput]:
        task_status = TaskStatus(status) if status else None
        tasks = runtime.executor.list_tasks(
            status=task_status, task_type=task_type, limit=limit,
        )
        return TasksOutput(tasks=[
            TaskOutput.model_validate(json_safe({
                "task_id": task.task_id,
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "metadata": task.metadata,
            }))
            for task in tasks
        ])
