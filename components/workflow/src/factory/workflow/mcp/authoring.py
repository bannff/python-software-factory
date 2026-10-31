"""Typed authoring MCP tools for Workflow."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator

from .contracts.authoring import (
    AuthoringStatusOutput, DefinitionOutput, DeleteWorkflowInput, UpsertWorkflowInput,
    ValidateWorkflowsInput, ValidationOutput,
)
from .contracts.base import EmptyInput, json_safe

if TYPE_CHECKING:
    from ..authoring import AuthoringManager
    from ..runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: "WorkflowRuntime", manager: "AuthoringManager | None") -> None:
    """Register strict authoring Workflow tools."""
    from ..authoring import AuthoringError

    @mcp.tool(name="workflow.authoring.get_status")
    @authoring_decorator(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        status = {"enabled": False, "config_dir": str(runtime.config_dir)} if not manager else manager.get_status()
        return AuthoringStatusOutput.model_validate(status)

    @mcp.tool(name="workflow.authoring.validate_workflows")
    @authoring_decorator(input_model=ValidateWorkflowsInput, output_model=ValidationOutput)
    def authoring_validate_workflows(dry_run: bool = True) -> ToolResult[ValidationOutput]:
        if not manager:
            raise AuthoringError("Authoring tools disabled")
        return ValidationOutput.model_validate(json_safe(manager.validate_all_workflows()))

    @mcp.tool(name="workflow.authoring.upsert_workflow_definition")
    @authoring_decorator(input_model=UpsertWorkflowInput, output_model=DefinitionOutput)
    def authoring_upsert_workflow_definition(id: str, yaml_or_object: str | dict, dry_run: bool = False) -> ToolResult[DefinitionOutput]:
        if not manager:
            raise AuthoringError("Authoring tools disabled")
        return DefinitionOutput.model_validate(json_safe(manager.upsert_workflow_definition(id=id, yaml_or_object=yaml_or_object, dry_run=dry_run)))

    @mcp.tool(name="workflow.authoring.delete_workflow_definition")
    @authoring_decorator(input_model=DeleteWorkflowInput, output_model=DefinitionOutput)
    def authoring_delete_workflow_definition(id: str) -> ToolResult[DefinitionOutput]:
        if not manager:
            raise AuthoringError("Authoring tools disabled")
        return DefinitionOutput.model_validate(json_safe(manager.delete_workflow_definition(id=id)))
