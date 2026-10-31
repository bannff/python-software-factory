"""Activity and graph-context stream views for the Sandbox brick.

Exports:
- activity_stream(): compact cross-brick sandbox activity lane
- graph_context_stream(): related graph entities anchoring sandbox activity

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def activity_stream() -> dict[str, Any]:
    """Recent sandbox activity shown as a compact cross-brick activity lane."""
    return {
        "id": "sb-activity-stream",
        "type": "item_list",
        "props": {
            "data_tool": "sandbox_get_dashboard_summary",
            "data_path": "$.recent_activity",
            "item_key": "event_id",
            "empty_icon": "pulse",
            "empty_message": "No sandbox activity recorded yet. Recent workflow-driven environment actions will appear here.",
            "header": {
                "icon": "pulse",
                "stats_tool": "sandbox_get_dashboard_summary",
                "stats_map": {
                    "activity": "$.overview.activity",
                    "envs": "$.overview.environments",
                },
            },
            "filters": {
                "field": "event_type",
                "values": [
                    "sandbox.provisioned",
                    "sandbox.command_executed",
                    "sandbox.file_uploaded",
                    "sandbox.file_downloaded",
                    "sandbox.terminated",
                    "sandbox.status_observed",
                    "sandbox.container_reaped",
                ],
                "colors": {
                    "sandbox.provisioned": "emerald",
                    "sandbox.command_executed": "blue",
                    "sandbox.file_uploaded": "purple",
                    "sandbox.file_downloaded": "yellow",
                    "sandbox.terminated": "red",
                    "sandbox.status_observed": "gray",
                    "sandbox.container_reaped": "orange",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.label",
                "subtitle": "$.env_id",
                "badge": {"field": "event_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.age_label", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Environment", "path": "$.env_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Run", "path": "$.run_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Profile", "path": "$.profile", "render_as": "pills", "zone": "config"},
                    {"label": "Status", "path": "$.status", "zone": "config"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Timestamp", "path": "$.timestamp", "render_as": "relative_time", "zone": "identity"},
                ],
            },
        },
    }


def graph_context_stream() -> dict[str, Any]:
    """Related graph entities that anchor sandbox activity into the wider system."""
    return {
        "id": "sb-graph-context",
        "type": "item_list",
        "props": {
            "data_tool": "sandbox_get_dashboard_summary",
            "data_path": "$.related_graph_entities",
            "item_key": "entity_id",
            "empty_icon": "network",
            "empty_message": "No related graph entities yet. Graph-backed sandbox runs will surface linked entities here.",
            "header": {
                "icon": "network",
                "stats_tool": "sandbox_get_dashboard_summary",
                "stats_map": {
                    "entities": "$.overview.graph_entities",
                    "envs": "$.overview.environments",
                },
            },
            "filters": {
                "field": "entity_type",
                "values": [
                    "SandboxEnvironment",
                    "WorkflowRun",
                    "WorkflowStep",
                    "EvaluationRun",
                    "Event",
                    "Metric",
                    "Finding",
                ],
                "colors": {
                    "SandboxEnvironment": "emerald",
                    "WorkflowRun": "blue",
                    "WorkflowStep": "sky",
                    "EvaluationRun": "amber",
                    "Event": "slate",
                    "Metric": "violet",
                    "Finding": "red",
                },
                "show_counts": False,
            },
            "item_layout": {
                "title": "$.title",
                "subtitle": "$.subtitle",
                "badge": {"field": "entity_type", "color_map": "filters.colors", "suffix": ""},
                "value": {"path": "$.focus_env_id", "format": "text"},
            },
            "detail": {
                "metadata": [
                    {"label": "Entity", "path": "$.entity_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Type", "path": "$.entity_type", "render_as": "pills", "zone": "identity"},
                    {"label": "Sandbox Env", "path": "$.focus_env_id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Detail", "path": "$.detail", "render_as": "popover", "zone": "config"},
                    {"label": "Properties", "path": "$.properties", "render_as": "popover", "zone": "config"},
                ],
            },
        },
    }
