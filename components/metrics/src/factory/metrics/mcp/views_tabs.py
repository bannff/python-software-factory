"""Tab and action builders for Metrics dashboard.

Exports:
- metrics_read_tabs(): read-only tabs component
- metrics_actions(): re-exported from views_actions for backward compat

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any

from .views_actions import metrics_actions  # noqa: F401 — re-export


# ── Read-only tabs ─────────────────────────────────────────────────


def metrics_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only metrics data."""
    return {
        "id": "metrics-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {
                    "id": "registry",
                    "label": "Registry",
                    "lazy_tool": "metrics_get_registry",
                    "result_hints": {"searchable": True, "sortable": True},
                },
                {
                    "id": "snapshots",
                    "label": "Snapshots",
                    "lazy_tool": "metrics_get_registry",
                    "result_hints": {"prefer": "stat_grid"},
                },
                # trends and drift moved to item_list detail.tabs in views.py
                {
                    "id": "taxonomy",
                    "label": "Taxonomy",
                    "lazy_tool": "metrics_get_by_taxonomy",
                    "result_hints": {
                        "prefer": "grouped_table",
                        "group_by": "domain",
                        "columns": [
                            {"key": "id", "label": "ID"},
                            {"key": "name", "label": "Name"},
                            {"key": "domain", "label": "Domain"},
                            {"key": "category", "label": "Category"},
                            {"key": "source_brick", "label": "Source"},
                            {"key": "format", "label": "Format"},
                        ],
                        "searchable": True,
                        "sortable": True,
                        "tooltip": "Browse metrics grouped by domain and category",
                    },
                },
            ],
        },
    }
