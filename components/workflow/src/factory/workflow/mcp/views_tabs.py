"""Tab and action builders for Workflow dashboard.

Exports:
- workflow_read_tabs(): read-only tabs (runs, tasks, registry, health)
- workflow_actions(): write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def workflow_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only workflow data."""
    return {
        "id": "workflow-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "runs", "label": "Active Runs",
                 "lazy_tool": "workflow.list_runs",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "tasks", "label": "Executor Tasks",
                 "lazy_tool":
                     "workflow.executor.list_tasks",
                 "result_hints": {"searchable": True}},
                {"id": "registry", "label": "Registry",
                 "lazy_tool":
                     "workflow.get_workflow_registry",
                 "result_hints": {"searchable": True}},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "workflow.health_check",
                 "result_hints": {"prefer": "stat_grid"}},
            ],
        },
    }


def workflow_actions() -> list[dict[str, Any]]:
    """Return action definitions for the workflow action pane."""
    return [
        _get_run(), _cancel_run(), _resume_run(),
        _step_run(), _emit_event(),
        _save_definition(), _delete_definition(),
    ]


def _get_run() -> dict[str, Any]:
    return {
        "id": "get-run", "label": "Get Run Details", "icon": "🔍",
        "tool": "workflow.get_run",
        "submit_label": "Fetch",
        "fields": [
            {"name": "run_id", "label": "Run ID", "type": "text",
             "placeholder": "UUID of the run to inspect",
             "tooltip": "Retrieve full state and step history"},
        ],
    }


def _cancel_run() -> dict[str, Any]:
    return {
        "id": "cancel-run", "label": "Cancel Run", "icon": "⛔",
        "tool": "workflow.cancel_run",
        "submit_label": "Cancel Run",
        "fields": [
            {"name": "run_id", "label": "Run ID", "type": "text",
             "placeholder": "UUID of the run to cancel",
             "tooltip": "Unique identifier of the workflow run"},
            {"name": "reason", "label": "Reason", "type": "text",
             "placeholder": "Optional cancellation reason",
             "tooltip": "Human-readable reason for cancelling"},
        ],
    }


def _resume_run() -> dict[str, Any]:
    return {
        "id": "resume-run", "label": "Resume Run", "icon": "▶️",
        "tool": "workflow.resume_run",
        "submit_label": "Resume",
        "fields": [
            {"name": "run_id", "label": "Run ID", "type": "text",
             "placeholder": "UUID of the paused run",
             "tooltip": "Unique identifier of the paused run"},
        ],
    }


def _step_run() -> dict[str, Any]:
    return {
        "id": "step-run", "label": "Step Run", "icon": "⏭️",
        "tool": "workflow.step_run",
        "submit_label": "Step",
        "fields": [
            {"name": "run_id", "label": "Run ID", "type": "text",
             "placeholder": "UUID of the run to step",
             "tooltip": "Advance this run by exactly one step"},
        ],
    }


def _emit_event() -> dict[str, Any]:
    return {
        "id": "emit-event", "label": "Emit Event", "icon": "📡",
        "tool": "workflow.emit_event",
        "submit_label": "Emit",
        "fields": [
            {"name": "run_id", "label": "Run ID", "type": "text",
             "placeholder": "UUID of the target run",
             "tooltip": "Workflow run that should receive this event"},
            {"name": "event_type", "label": "Event Type", "type": "text",
             "placeholder": "e.g. approval_granted",
             "tooltip": "Event type the workflow is waiting for"},
            {"name": "payload", "label": "Payload (JSON)",
             "type": "textarea", "placeholder": "{}",
             "tooltip": "JSON payload attached to the event"},
        ],
    }


def _save_definition() -> dict[str, Any]:
    return {
        "id": "save-def", "label": "Save Definition", "icon": "💾",
        "tool": "workflow.authoring.upsert_workflow_definition",
        "submit_label": "Save Definition",
        "fields": [
            {"name": "id", "label": "Workflow ID", "type": "text",
             "placeholder": "my-workflow",
             "tooltip": "Unique identifier for this definition"},
            {"name": "yaml_or_object", "label": "Definition (YAML/JSON)",
             "type": "textarea",
             "placeholder": '{"steps": [{"name": "s1", "type": "task"}]}',
             "tooltip": "Full workflow definition as YAML or JSON"},
        ],
    }


def _delete_definition() -> dict[str, Any]:
    return {
        "id": "delete-def", "label": "⚠ Delete Definition", "icon": "🗑️",
        "tool": "workflow.authoring.delete_workflow_definition",
        "submit_label": "Delete",
        "fields": [
            {"name": "id", "label": "Workflow ID", "type": "text",
             "placeholder": "my-workflow",
             "tooltip": "ID of the definition to permanently remove"},
        ],
    }
