"""Fleet-summary and profile catalog views for the Sandbox brick.

Exports:
- status_mix_chart(): quick visual summary of environment state mix
- profiles_list(): built-in target profiles presented as a launch catalog

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def status_mix_chart() -> dict[str, Any]:
    """Quick visual summary of environment state mix."""
    return {
        "id": "sb-status-mix",
        "type": "chart",
        "props": {
            "title": "Environment Status Mix",
            "data_tool": "sandbox_get_dashboard_summary",
            "xKey": "label",
            "yKey": "value",
            "empty_state": "Provision a sandbox to populate the fleet overview.",
            "className": "mb-3",
        },
    }


def profiles_list() -> dict[str, Any]:
    """Built-in target profiles presented as a launch catalog."""
    return {
        "id": "sb-profiles",
        "type": "item_list",
        "props": {
            "data_tool": "sandbox_get_dashboard_summary",
            "data_path": "$.profiles",
            "item_key": "name",
            "empty_icon": "beaker",
            "empty_message": "No target profiles available.",
            "header": {
                "icon": "beaker",
                "stats_tool": "sandbox_get_dashboard_summary",
                "stats_map": {
                    "profiles": "$.overview.profiles",
                    "adapter": "$.overview.adapter",
                },
            },
            "item_layout": {
                "title": "$.name",
                "subtitle": "$.image",
                "badge": {"field": "active_count", "suffix": " active"},
                "value": {
                    "path": "$.port_count",
                    "format": "number",
                },
            },
            "detail": {
                "metadata": [
                    {"label": "Image", "path": "$.image", "render_as": "popover", "zone": "config"},
                    {"label": "Health URL", "path": "$.health_check_url", "render_as": "copy_id", "zone": "config"},
                    {"label": "Container", "path": "$.container_name", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Shell", "path": "$.shell", "render_as": "pills", "zone": "identity"},
                    {"label": "Ports", "path": "$.ports", "render_as": "pills", "zone": "config"},
                    {"label": "Health Timeout", "path": "$.health_timeout", "zone": "identity"},
                ],
            },
        },
    }
