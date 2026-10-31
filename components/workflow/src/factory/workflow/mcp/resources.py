"""MCP Resource registration for Workflow brick.

Resources expose static/queryable data:
- Schemas for workflow definitions and settings
- Documentation on step kinds and executors
- Live workflow registry and run details
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import WORKFLOW_DOCS

if TYPE_CHECKING:
    from factory.workflow.runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: "WorkflowRuntime") -> None:
    """Register all Workflow resources with the MCP server."""
    from factory.workflow.runtime.models import WorkflowDefinition, Settings, ExecutorSettings

    # Schema resources
    @mcp.resource("workflow://schemas/definition")
    def resource_definition_schema() -> str:
        """Get the JSON schema for workflow definitions."""
        return json.dumps(WorkflowDefinition.model_json_schema(), indent=2)

    @mcp.resource("workflow://schemas/settings")
    def resource_settings_schema() -> str:
        """Get the JSON schema for workflow settings."""
        return json.dumps(Settings.model_json_schema(), indent=2)

    @mcp.resource("workflow://schemas/executor")
    def resource_executor_schema() -> str:
        """Get executor configuration options."""
        return json.dumps(ExecutorSettings.model_json_schema(), indent=2)

    # Documentation resources
    @mcp.resource("workflow://docs")
    def resource_docs_list() -> str:
        """List available workflow documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in WORKFLOW_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("workflow://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get workflow documentation by name."""
        if doc_name in WORKFLOW_DOCS:
            return WORKFLOW_DOCS[doc_name]["content"]
        available = list(WORKFLOW_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    # Live data resources
    @mcp.resource("workflow://workflows")
    def resource_workflows() -> str:
        """List all registered workflow definitions."""
        registry = runtime.get_workflow_registry()
        return json.dumps({"workflows": registry, "count": len(registry)}, indent=2)

    @mcp.resource("workflow://runs/{run_id}")
    def resource_run(run_id: str) -> str:
        """Get details of a specific workflow run."""
        from factory.workflow.runtime.envelope import Envelope
        try:
            run = runtime.get_run(run_id=run_id, envelope=Envelope())
            return json.dumps(run, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e), "run_id": run_id})

    # Cross-reference to factory
    @mcp.resource("workflow://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": [
                "foreman_info", "foreman_check", 
                "foreman_guardian_check", "foreman_get_repo_guardrails",
            ],
            "foreman_resources": [
                "foreman://docs", "foreman://bricks", "foreman://schema/brick-yaml",
            ],
        }, indent=2)
