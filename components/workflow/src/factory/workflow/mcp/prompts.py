"""MCP Prompt registration for Workflow brick.

Prompts provide guided workflows for common tasks:
- Creating new workflow definitions
- Debugging stuck or failed runs
- Configuring executor backends
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import PROMPT_TEMPLATES, EXECUTOR_GUIDES

if TYPE_CHECKING:
    from factory.workflow.runtime.runtime import WorkflowRuntime


def register(mcp: Any, runtime: "WorkflowRuntime") -> None:
    """Register all Workflow prompts with the MCP server."""

    @mcp.prompt()
    def create_workflow(name: str, purpose: str = "", tags: str = "") -> str:
        """Generate guidance for creating a new workflow definition."""
        workflow_id = name.lower().replace(" ", "-").replace("_", "-")
        
        steps_yaml = """  - id: start
    kind: noop
    next: process
  - id: process
    kind: task
    task_type: main_task
    next: end
  - id: end
    kind: noop"""
        
        return PROMPT_TEMPLATES["create_workflow"]["template"].format(
            name=name,
            id=workflow_id,
            purpose=purpose or f"Workflow for {name}",
            tags=tags or "general",
            steps_yaml=steps_yaml,
        )

    @mcp.prompt()
    def debug_run(run_id: str) -> str:
        """Generate guidance for debugging a workflow run."""
        from factory.workflow.runtime.envelope import Envelope
        try:
            run = runtime.get_run(run_id=run_id, envelope=Envelope())
            status_info = f"""- Status: {run.get('status', 'unknown')}
- Current Step: {run.get('current_step_id', 'N/A')}
- Waiting For: {run.get('waiting_for_event_type', 'N/A')}
- Error: {run.get('error', 'None')}"""
        except Exception:
            status_info = "(Unable to fetch run details - run may not exist)"
        
        return PROMPT_TEMPLATES["debug_run"]["template"].format(
            run_id=run_id,
            status_info=status_info,
        )

    @mcp.prompt()
    def configure_executor(backend: str = "celery") -> str:
        """Generate guidance for configuring a task executor backend."""
        backend = backend.lower()
        if backend not in EXECUTOR_GUIDES:
            backend = "celery"
        
        guide = EXECUTOR_GUIDES[backend]
        current_config = f"Currently using: {runtime.executor.backend_name}"
        
        return PROMPT_TEMPLATES["configure_executor"]["template"].format(
            backend=backend,
            current_config=current_config,
            setup_guide=guide["setup_guide"],
            backend_config=guide["backend_config"],
        )
