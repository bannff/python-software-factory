"""UIView definitions for Storage brick.

Uses the page skeleton for standardized 3-zone layout.
Zone 3 uses an action_pane component — a single dropdown selector
with dynamic forms — instead of multiple collapsible forms.
"""

from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.base import EmptyInput
from .contracts.deterministic import ViewsOutput
from .views_tabs import storage_actions, storage_read_tabs


def register(mcp: Any) -> None:
    """Register Storage view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def storage_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Storage brick."""
        return ViewsOutput(views=[
            {
                "id": "storage-browser",
                "name": "Storage Browser",
                "brick": "storage",
                "icon": "💾",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    {
                        "id": "storage-page",
                        "type": "page",
                        "props": {
                            "title": "Storage Browser",
                            "subtitle": (
                                "Browse blob, document, SQL,"
                                " and graph storage backends"
                            ),
                            "icon": "💾",
                            "gradient": "from-sky-500 to-blue-600",
                            "tooltip": (
                                "Unified storage abstraction"
                                " across multiple backends"
                            ),
                        },
                        "children": _children(),
                    },
                ],
                "metadata": {
                    "description": "Browse blob, document, SQL, and graph storage",
                    "nav_label": "Storage",
                    "nav_order": 40,
                },
            },
        ])


def _children() -> list[dict[str, object]]:
    """Build page children: metrics, list form, read tabs, action pane."""
    return [
        # ── Zone 2: Info metrics ──
        {
            "id": "storage-stat-blob",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Blob",
                "value": "local_fs", "icon": "document",
                "tooltip": "Blob storage backend (local_fs, S3, etc.)",
            },
        },
        {
            "id": "storage-stat-doc",
            "type": "metric",
            "props": {
                "zone": "info", "label": "Document",
                "value": "tinydb", "icon": "document",
                "tooltip": "Document store backend (TinyDB, MongoDB, etc.)",
            },
        },
        # ── Zone 2: Controls — primary list form ──
        {
            "id": "storage-blob-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "storage_blob_list",
                "title": "Browse Files",
                "submit_label": "List Files",
                "fields": [
                    {
                        "name": "prefix",
                        "label": "Path Prefix",
                        "type": "text",
                        "placeholder": "/",
                        "tooltip": "Filter blobs by key prefix",
                    },
                    {
                        "name": "limit",
                        "label": "Max Results",
                        "type": "range",
                        "min": 1, "max": 100, "value": 25,
                        "tooltip": "Cap the number of returned blobs",
                    },
                ],
            },
        },
        # ── Zone 3: Read-only tabs (lazy-loaded data) ──
        storage_read_tabs(),
        # ── Zone 3: Action pane (polymorphic write operations) ──
        {
            "id": "storage-actions",
            "type": "action_pane",
            "props": {
                "actions": storage_actions(),
                "default_action": "upload-blob",
            },
        },
    ]
