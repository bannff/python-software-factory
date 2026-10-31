"""Workflow dashboard views with summary, activity, and graph context."""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.base import EmptyInput, json_safe
from .contracts.views import ActivityInput, DashboardOutput, EntriesOutput, GraphContextInput, RunTasksInput, ViewsOutput

from ..runtime.runtime import WorkflowRuntime
from .dashboard_summary import (
    build_dashboard_summary,
    list_executor_tasks,
    list_recent_activity,
    list_related_graph_entities,
)
from .views_tabs import workflow_actions

def register(mcp: Any, runtime: WorkflowRuntime) -> None:
    """Register Workflow view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardOutput)
    def workflow_get_dashboard_summary() -> ToolResult[DashboardOutput]:
        """Return aggregate workflow dashboard data."""
        return DashboardOutput.model_validate(json_safe(build_dashboard_summary(runtime)))

    @mcp.tool()
    @deterministic(input_model=ActivityInput, output_model=EntriesOutput)
    def workflow_get_run_activity(run_id: str, limit: int = 20) -> ToolResult[EntriesOutput]:
        """Return recent shared activity for a workflow run."""
        entries = list_recent_activity(limit=limit, run_id=run_id)
        return EntriesOutput.model_validate(json_safe({"run_id": run_id, "entries": entries, "count": len(entries)}))

    @mcp.tool()
    @deterministic(input_model=GraphContextInput, output_model=EntriesOutput)
    def workflow_get_run_graph_context(run_id: str, limit: int = 12) -> ToolResult[EntriesOutput]:
        """Return related graph entities for a workflow run."""
        entries = list_related_graph_entities(limit=limit, run_id=run_id)
        return EntriesOutput.model_validate(json_safe({"run_id": run_id, "entries": entries, "count": len(entries)}))

    @mcp.tool()
    @deterministic(input_model=RunTasksInput, output_model=EntriesOutput)
    def workflow_get_run_tasks(run_id: str, limit: int = 20) -> ToolResult[EntriesOutput]:
        """Return executor tasks associated with a workflow run."""
        entries = list_executor_tasks(runtime, run_id=run_id, limit=limit)
        return EntriesOutput.model_validate(json_safe({"run_id": run_id, "entries": entries, "count": len(entries)}))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def workflow_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Workflow brick."""
        return ViewsOutput(views=[
            {
                "id": "workflow-dashboard",
                "name": "Workflows",
                "brick": "workflow",
                "icon": "⚙️",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    _status_mix_chart(),
                    _start_form(),
                    _runs_list(),
                    _tasks_list(),
                    _activity_stream(),
                    _graph_context_stream(),
                    _action_pane(),
                ],
                "metadata": {
                    "description": "Start and monitor workflow executions",
                    "nav_label": "Workflows",
                    "nav_order": 45,
                },
            },
        ])

def _status_mix_chart() -> dict[str, Any]:
    return {
        "id": "workflow-status-mix",
        "type": "chart",
        "props": {
            "title": "Run Status Mix",
            "data_tool": "workflow_get_dashboard_summary",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Start a workflow to populate the execution overview.",
            "className": "mb-3",
        },
    }

def _start_form() -> dict[str, Any]:
    return {
        "id": "workflow-start-form",
        "type": "form",
        "props": {
            "tool": "workflow.start_run",
            "title": "Start Workflow",
            "submit_label": "Start Workflow",
            "description": "Launch a run with optional correlated input payload.",
            "fields": [
                {
                    "name": "workflow_name_or_id",
                    "label": "Workflow",
                    "type": "text",
                    "placeholder": "example",
                    "tooltip": "Workflow definition name or ID",
                },
                {
                    "name": "input",
                    "label": "Input (JSON)",
                    "type": "textarea",
                    "placeholder": '{"env_id": "env-123", "target_app": "WebGoat"}',
                    "tooltip": "JSON payload passed into the workflow run",
                },
            ],
        },
    }

def _runs_list() -> dict[str, Any]:
    return {
        "id": "workflow-runs",
        "type": "item_list",
        "props": {
            "data_tool": "workflow_get_dashboard_summary",
            "data_path": "$.runs",
            "item_key": "run_id",
            "empty_icon": "play",
            "empty_message": "No workflow runs yet.",
            "header": {
                "icon": "play",
                "stats_tool": "workflow_get_dashboard_summary",
                "stats_map": {
                    "runs": "$.overview.runs",
                    "running": "$.overview.running",
                    "waiting": "$.overview.waiting",
                },
            },
            "filters": {
                "field": "status",
                "values": ["running", "waiting", "pending", "succeeded", "failed", "cancelled"],
                "colors": {
                    "running": "blue",
                    "waiting": "amber",
                    "pending": "slate",
                    "succeeded": "emerald",
                    "failed": "red",
                    "cancelled": "gray",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.workflow_name",
                "subtitle": "$.run_id",
                "badge": {"field": "status", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.age_label", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Workflow ID", "path": "$.workflow_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Status", "path": "$.status", "render_as": "pills", "zone": "identity"},
                    {"label": "Current Step", "path": "$.current_step_id", "zone": "config"},
                    {"label": "Waiting For", "path": "$.waiting_for_event_type", "zone": "config"},
                    {"label": "Activity", "path": "$.activity_count", "zone": "identity"},
                    {"label": "Tasks", "path": "$.task_count", "zone": "identity"},
                    {"label": "Last Activity", "path": "$.last_activity_label", "zone": "config"},
                    {"label": "Tenant", "path": "$.tenant_id", "zone": "identity"},
                    {"label": "Input", "path": "$.input", "render_as": "popover", "zone": "config"},
                    {"label": "Result", "path": "$.result", "render_as": "popover", "zone": "config"},
                    {"label": "Error", "path": "$.error", "render_as": "popover", "zone": "config"},
                    {"label": "Started", "path": "$.started_at", "render_as": "relative_time", "zone": "identity"},
                    {"label": "Updated", "path": "$.updated_at", "render_as": "relative_time", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "run",
                        "label": "Run",
                        "tool": "workflow.get_run",
                        "args": {"run_id": "$.run_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "activity",
                        "label": "Activity",
                        "tool": "workflow_get_run_activity",
                        "args": {"run_id": "$.run_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No recorded activity for this run yet.",
                    },
                    {
                        "id": "tasks",
                        "label": "Tasks",
                        "tool": "workflow_get_run_tasks",
                        "args": {"run_id": "$.run_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No executor tasks recorded for this run yet.",
                    },
                    {
                        "id": "graph",
                        "label": "Graph",
                        "tool": "workflow_get_run_graph_context",
                        "args": {"run_id": "$.run_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No related graph entities found for this run yet.",
                    },
                ],
            },
        },
    }

def _tasks_list() -> dict[str, Any]:
    return {
        "id": "workflow-tasks",
        "type": "item_list",
        "props": {
            "data_tool": "workflow_get_dashboard_summary",
            "data_path": "$.tasks",
            "item_key": "task_id",
            "empty_icon": "cpu-chip",
            "empty_message": "No executor tasks yet.",
            "header": {
                "icon": "cpu-chip",
                "stats_tool": "workflow_get_dashboard_summary",
                "stats_map": {
                    "tasks": "$.overview.tasks",
                    "executor": "$.overview.executor",
                },
            },
            "filters": {
                "field": "status",
                "values": ["running", "pending", "succeeded", "failed", "cancelled"],
                "colors": {
                    "running": "blue",
                    "pending": "slate",
                    "succeeded": "emerald",
                    "failed": "red",
                    "cancelled": "gray",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.task_id",
                "subtitle": "$.run_id",
                "badge": {"field": "status", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.step_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Task", "path": "$.task_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Step", "path": "$.step_id", "zone": "identity"},
                    {"label": "Status", "path": "$.status", "render_as": "pills", "zone": "identity"},
                    {"label": "Task Type", "path": "$.task_type", "zone": "config"},
                    {"label": "Result", "path": "$.result", "render_as": "popover", "zone": "config"},
                    {"label": "Error", "path": "$.error", "render_as": "popover", "zone": "config"},
                    {"label": "Metadata", "path": "$.metadata", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }

def _activity_stream() -> dict[str, Any]:
    return {
        "id": "workflow-activity-stream",
        "type": "item_list",
        "props": {
            "data_tool": "workflow_get_dashboard_summary",
            "data_path": "$.recent_activity",
            "item_key": "event_id",
            "empty_icon": "pulse",
            "empty_message": "No workflow activity recorded yet.",
            "header": {
                "icon": "pulse",
                "stats_tool": "workflow_get_dashboard_summary",
                "stats_map": {
                    "activity": "$.overview.activity",
                    "runs": "$.overview.runs",
                },
            },
            "filters": {
                "field": "event_type",
                "values": ["workflow.run_started", "workflow.step_transition", "workflow.event_emitted", "workflow.run_cancelled", "workflow.run_failed"],
                "colors": {
                    "workflow.run_started": "emerald",
                    "workflow.step_transition": "blue",
                    "workflow.event_emitted": "amber",
                    "workflow.run_cancelled": "gray",
                    "workflow.run_failed": "red",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.label",
                "subtitle": "$.run_id",
                "badge": {"field": "event_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.age_label", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Workflow", "path": "$.workflow_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Step", "path": "$.step", "zone": "config"},
                    {"label": "Status", "path": "$.status", "zone": "config"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
            },
        },
    }

def _graph_context_stream() -> dict[str, Any]:
    return {
        "id": "workflow-graph-context",
        "type": "item_list",
        "props": {
            "data_tool": "workflow_get_dashboard_summary",
            "data_path": "$.related_graph_entities",
            "item_key": "entity_id",
            "empty_icon": "network",
            "empty_message": "No related graph entities yet.",
            "header": {
                "icon": "network",
                "stats_tool": "workflow_get_dashboard_summary",
                "stats_map": {
                    "entities": "$.overview.graph_entities",
                    "runs": "$.overview.runs",
                },
            },
            "filters": {
                "field": "entity_type",
                "values": ["WorkflowRun", "WorkflowDefinition", "WorkflowEvent", "SandboxEnvironment", "GameSession", "Metric", "Finding"],
                "colors": {
                    "WorkflowRun": "blue",
                    "WorkflowDefinition": "amber",
                    "WorkflowEvent": "sky",
                    "SandboxEnvironment": "emerald",
                    "GameSession": "violet",
                    "Metric": "indigo",
                    "Finding": "red",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.title",
                "subtitle": "$.subtitle",
                "badge": {"field": "entity_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.focus_run_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Run", "path": "$.focus_run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }

def _action_pane() -> dict[str, Any]:
    return {
        "id": "workflow-actions",
        "type": "action_pane",
        "props": {
            "actions": workflow_actions(),
            "default_action": "get-run",
        },
    }
