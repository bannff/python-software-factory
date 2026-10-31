"""Typed deterministic MCP tools for Workflow."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.base import EmptyInput, json_safe
from .contracts.deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, ExecutorStatusOutput, HealthOutput,
    WorkflowRegistryOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: "WorkflowRuntime") -> None:
    """Register strict deterministic Workflow tools."""

    @mcp.tool(name="workflow.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return CapabilitiesOutput.model_validate(json_safe(runtime.get_capabilities()))

    @mcp.tool(name="workflow.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        return HealthOutput.model_validate(json_safe(runtime.health_check()))

    @mcp.tool(name="workflow.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ConfigSchemaOutput.model_validate(json_safe(runtime.describe_config_schema()))

    @mcp.tool(name="workflow.get_workflow_registry")
    @deterministic(input_model=EmptyInput, output_model=WorkflowRegistryOutput)
    def get_workflow_registry() -> ToolResult[WorkflowRegistryOutput]:
        return WorkflowRegistryOutput(workflows=runtime.get_workflow_registry())

    @mcp.tool(name="workflow.executor.get_status")
    @deterministic(input_model=EmptyInput, output_model=ExecutorStatusOutput)
    def executor_get_status() -> ToolResult[ExecutorStatusOutput]:
        status = json_safe(runtime.executor.health_check())
        assert isinstance(status, dict)
        return ExecutorStatusOutput(
            ok=bool(status.get("ok", False)), backend=str(status.get("backend", "")),
            details=status,
        )
