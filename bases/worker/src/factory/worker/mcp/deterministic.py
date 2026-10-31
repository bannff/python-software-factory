"""Typed deterministic MCP tools for the Worker base."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput,
    ConfigSchemaOutput,
    HealthOutput,
    TaskListOutput,
)
from .projections import health_payload, task_payload

if TYPE_CHECKING:
    from ..runtime.runtime import WorkerRuntime


def register(mcp: Any, get_runtime: Callable[[], "WorkerRuntime"]) -> None:
    """Register the Worker deterministic surface with strict DTOs."""

    @typed_tool(mcp, name="worker_get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def worker_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable Worker capabilities."""
        return {
            "name": "worker",
            "version": "1.0.0",
            "backends": get_runtime().available_backends(),
            "features": [
                "background_tasks",
                "task_execution",
                "health_monitoring",
                "mcp_bridge",
            ],
        }

    @typed_tool(mcp, name="worker_health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def worker_health_check() -> ToolResult[HealthOutput]:
        """Return a redacted worker readiness probe."""
        runtime = get_runtime()
        return health_payload(runtime.health_check(), runtime.available_backends())

    @typed_tool(mcp, name="worker_describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def worker_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe supported Worker configuration."""
        return {
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["celery", "dagster", "fargate_sqs"],
                    "description": "Worker backend type",
                },
                "broker_url": {
                    "type": "string",
                    "description": "Celery broker URL or Fargate SQS queue URL",
                },
                "queues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Queues to consume from",
                },
            },
            "unsupported": ["concurrency"],
        }

    @typed_tool(mcp, name="worker_list_tasks")
    @deterministic(input_model=EmptyInput, output_model=TaskListOutput)
    def worker_list_tasks() -> ToolResult[TaskListOutput]:
        """List registered or pending tasks without provider diagnostics."""
        try:
            tasks = get_runtime().list_tasks()
        except Exception:
            return {"tasks": [], "count": 0, "error": "worker_tasks_unavailable"}
        projected = [task_payload(task) for task in tasks]
        return {"tasks": projected, "count": len(projected), "error": None}


__all__ = ["register"]
