"""UIView definitions for Cache brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of tabs with redundant forms.
"""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts.base import EmptyInput
from .contracts.views import CacheViewsOutput
from .views_tabs import cache_actions, cache_read_tabs


def register(mcp: Any) -> None:
    """Register Cache view definitions."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CacheViewsOutput)
    def cache_get_views() -> ToolResult[CacheViewsOutput]:
        """Return UIView definitions for the Cache brick."""
        EmptyInput.model_validate({})
        return ok(CacheViewsOutput.model_validate({"views": [
            {
                "id": "cache-dashboard",
                "name": "Cache",
                "brick": "cache",
                "icon": "⚡",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "cache-page",
                        "type": "page",
                        "props": {
                            "title": "Cache",
                            "subtitle": (
                                "Inspect, set, and manage ephemeral"
                                " cache entries"
                            ),
                            "icon": "⚡",
                            "gradient": "from-cyan-500 to-blue-500",
                            "tooltip": (
                                "TTL-aware cache with polymorphic backends"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": "Inspect and manage cache entries",
                    "nav_label": "Cache",
                    "nav_order": 55,
                },
            },
        ]}))


def _children() -> list[dict[str, object]]:
    """Build page children: metrics, lookup form, read tabs, actions."""
    return [
        {
            "id": "cache-stat-status",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Status",
                "value": "Healthy", "icon": "check-circle",
                "intent": "success",
                "data_tool": "cache_health_check",
                "tooltip": "Cache backend health",
            },
        },
        {
            "id": "cache-stat-backend",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Backend",
                "value": "memory", "icon": "server-stack",
                "tooltip": "Polymorphic — swap to Redis, Memcached, etc.",
            },
        },
        {
            "id": "cache-lookup-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "cache_cache_get",
                "title": "Key Lookup",
                "submit_label": "Lookup",
                "fields": [
                    {
                        "name": "key",
                        "label": "Cache Key",
                        "type": "text",
                        "placeholder": "my:key",
                        "tooltip": "Exact key to look up",
                    },
                ],
            },
        },
        cache_read_tabs(),
        {
            "id": "cache-actions",
            "type": "action_pane",
            "props": {
                "actions": cache_actions(),
                "default_action": "set-value",
            },
        },
    ]
