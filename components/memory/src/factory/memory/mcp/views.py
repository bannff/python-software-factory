"""UIView definitions for Memory brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of multiple collapsible forms.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.runtime.tool_result import ToolResult

from .contracts.advanced import ViewsOutput
from .contracts.base import EmptyInput

from .views_tabs import memory_actions, memory_read_tabs


def register(mcp: Any) -> None:
    """Register Memory view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def memory_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Memory brick."""
        return {"views": [
            {
                "id": "memory-browser",
                "name": "Agent Memory",
                "brick": "memory",
                "icon": "🧠",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "memory-page",
                        "type": "page",
                        "props": {
                            "title": "Agent Memory",
                            "subtitle": (
                                "Browse, search, and manage agent"
                                " memories across sessions"
                            ),
                            "icon": "🧠",
                            "gradient": "from-violet-500 to-fuchsia-500",
                            "tooltip": (
                                "Semantic memory retrieval with"
                                " user-scoped isolation"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": "Browse and search agent memories",
                    "nav_label": "Memory",
                    "nav_order": 30,
                },
            },
        ]}


def _children() -> list[dict[str, Any]]:
    """Build page children: metrics, search form, read tabs, actions."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "memory-stat-count",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Memories",
                "value": "0", "icon": "document-text",
                "data_tool": "memory_memory_stats",
                "tooltip": "Total stored memory entries",
            },
        },
        {
            "id": "memory-stat-backend",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Backend",
                "value": "memory", "icon": "cpu-chip",
                "data_tool": "memory_health_check",
                "tooltip": "Polymorphic — swap to Zep, Cognee, Mem0, etc.",
            },
        },
        # ── Zone 2: Controls — primary search form ──
        {
            "id": "memory-search-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "memory_memory_retrieve",
                "title": "Search Memories",
                "submit_label": "Search Memories",
                "fields": [
                    {
                        "name": "query",
                        "label": "Query",
                        "type": "text",
                        "placeholder": "What do you remember about...",
                        "tooltip": "Semantic search across stored memories",
                    },
                    {
                        "name": "user_id",
                        "label": "User ID",
                        "type": "text",
                        "placeholder": "default",
                        "tooltip": "Scope retrieval to a specific user",
                    },
                    {
                        "name": "limit",
                        "label": "Max Results",
                        "type": "range",
                        "min": 1, "max": 50, "value": 10,
                        "tooltip": "Maximum number of memories to return",
                    },
                ],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        memory_read_tabs(),
        # ── Zone 3: Action pane (memory operations) ──
        {
            "id": "memory-actions",
            "type": "action_pane",
            "props": {
                "actions": memory_actions(),
                "default_action": "store-memory",
            },
        },
    ]
