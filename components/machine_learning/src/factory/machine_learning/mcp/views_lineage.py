"""Evidence-backed Lineage view declaration for the ML Observatory."""
from __future__ import annotations

from typing import Any

from .views_observatory import header


def lineage_view() -> dict[str, Any]:
    """Return the neutral supplied-data Lineage view."""
    return {
        "id": "ml-lineage", "name": "Lineage", "brick": "machine_learning",
        "icon": "🧬", "layout": {"type": "flex", "direction": "column"},
        "components": [
            header("Verified source references only; missing provenance stays visible."),
            {
                "id": "ml-lineage-graph", "type": "lineage",
                "props": {
                    "data_tool": "ml_get_observatory_lineage",
                    "empty_message": "Train a model or complete a learning run to create evidence-backed lineage.",
                },
            },
        ],
        "metadata": {
            "description": "Bounded evidence-only training and learning lineage",
            "nav_label": "Lineage", "nav_order": 54,
        },
    }


__all__ = ["lineage_view"]
