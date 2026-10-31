"""Environments fleet view for the Sandbox brick.

Exports:
- environments_list(): health-oriented item_list of sandbox + discovered targets

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def environments_list() -> dict[str, Any]:
    """Sandbox environments as a health-oriented fleet view."""
    return {
        "id": "sb-environments",
        "type": "item_list",
        "props": {
            "data_tool": "sandbox_get_dashboard_summary",
            "data_path": "$.environments",
            "item_key": "env_id",
            "empty_icon": "server-stack",
            "empty_message": (
                "No sandbox environments are currently visible. This page shows"
                " both sandbox-managed environments and discovered Docker vuln"
                " targets. If you started a target with docker compose, make sure"
                " it exposes either factory.sandbox=true or vuln.target labels."
            ),
            "header": {
                "icon": "server-stack",
                "stats_tool": "sandbox.health_check",
                "stats_map": {
                    "adapter": "$.adapter.adapter",
                    "discovered": "$.discovered_environments",
                    "docker": "$.adapter.docker_version",
                },
            },
            "filters": {
                "field": "status",
                "values": [
                    "running", "pending", "provisioning",
                    "terminated", "error",
                ],
                "colors": {
                    "running": "emerald",
                    "pending": "yellow",
                    "provisioning": "blue",
                    "terminated": "gray",
                    "error": "red",
                },
                "show_counts": True,
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.status",
                    "states": {
                        "running": "emerald",
                        "pending": "yellow",
                        "provisioning": "blue",
                        "terminated": "gray",
                        "error": "red",
                    },
                },
                "title": "$.env_id",
                "subtitle": "$.created_at",
                "badge": {
                    "field": "$.metadata.vuln.target",
                    "color_map": {
                        "vampi": "red",
                        "dvwa": "yellow",
                        "juice_shop": "orange",
                        "webgoat": "purple",
                        "idor_warehouse": "blue",
                    },
                    "suffix": "",
                },
                "value": {
                    "path": "$.status",
                    "format": "text",
                },
            },
            "detail": {
                "metadata": [
                    {"label": "Env ID", "path": "$.env_id",
                     "render_as": "copy_id", "zone": "identity"},
                    {"label": "Status", "path": "$.status",
                     "zone": "identity"},
                    {"label": "Target", "path": "$.metadata.vuln.target",
                     "zone": "identity"},
                    {"label": "Discovery", "path": "$.metadata.management",
                     "zone": "identity"},
                    {"label": "Instance", "path": "$.instance_type",
                     "render_as": "pills", "zone": "config"},
                    {"label": "Base URL", "path": "$.metadata.vuln.base_url",
                     "render_as": "copy_id", "zone": "config"},
                    {"label": "Compose Project", "path": "$.metadata.com.docker.compose.project",
                     "zone": "config"},
                    {"label": "Compose Service", "path": "$.metadata.com.docker.compose.service",
                     "zone": "config"},
                    {"label": "Profile", "path": "$.profile_name",
                     "render_as": "pills", "zone": "identity"},
                    {"label": "Age", "path": "$.age_label",
                     "zone": "identity"},
                    {"label": "Activity", "path": "$.activity_count",
                     "zone": "identity"},
                    {"label": "Last Activity", "path": "$.last_activity_label",
                     "zone": "config"},
                    {"label": "Ports", "path": "$.ports",
                     "render_as": "pills", "zone": "config"},
                    {"label": "Health URL", "path": "$.profile_health_url",
                     "render_as": "copy_id", "zone": "config"},
                    {"label": "Public IP", "path": "$.public_ip",
                     "render_as": "copy_id", "zone": "config"},
                    {"label": "Private IP", "path": "$.private_ip",
                     "render_as": "copy_id", "zone": "config"},
                    {"label": "Created", "path": "$.created_at",
                     "render_as": "relative_time",
                     "zone": "identity"},
                    {"label": "Metadata", "path": "$.metadata",
                     "render_as": "popover", "zone": "config"},
                ],
                "tabs": [
                    {
                        "id": "status",
                        "label": "Live Status",
                        "tool": "sandbox.get_status",
                        "args": {"env_id": "$.env_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "workspace",
                        "label": "Workspace",
                        "tool": "sandbox.workspace_dir",
                        "args": {"env_id": "$.env_id"},
                        "render_as": "json",
                    },
                    {
                        "id": "activity",
                        "label": "Activity",
                        "tool": "sandbox_get_environment_activity",
                        "args": {"env_id": "$.env_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No recorded activity for this environment yet.",
                    },
                    {
                        "id": "graph",
                        "label": "Graph",
                        "tool": "sandbox_get_environment_graph_context",
                        "args": {"env_id": "$.env_id", "limit": 12},
                        "data_path": "$.entries",
                        "render_as": "list",
                        "empty_message": "No related graph entities found for this environment yet.",
                    },
                ],
            },
        },
    }
