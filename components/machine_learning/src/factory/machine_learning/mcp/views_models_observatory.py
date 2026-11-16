"""Models view declaration for receipt artifacts and fine-tuning jobs."""
from __future__ import annotations

from typing import Any

from .views_finetuning import finetuning_jobs


def _receipt_models() -> dict[str, Any]:
    return {
        "id": "ml-receipt-models", "type": "item_list",
        "props": {
            "data_tool": "ml_get_observatory_summary", "data_path": "$.models",
            "item_key": "row_id", "empty_icon": "cube",
            "empty_message": "No receipt-backed model artifacts yet.",
            "header": {
                "icon": "cube", "stats_tool": "ml_get_observatory_summary",
                "stats_map": {"artifacts": "$.overview.receipt_models"},
            },
            "item_layout": {
                "title": "$.model_type", "subtitle": "$.artifact_uri",
                "badge": {"field": "source"},
            },
            "detail": {"metadata": [
                {"label": "Source Run", "path": "$.source_run_id", "render_as": "copy_id"},
                {"label": "Artifact URI", "path": "$.artifact_uri", "render_as": "copy_id"},
                {"label": "Canonical Model ID", "path": "$.entity_id"},
                {"label": "Provenance", "path": "$.provenance_state"},
                {"label": "Datasets", "path": "$.dataset_refs", "render_as": "pills"},
                {"label": "Evaluations", "path": "$.evaluation_refs", "render_as": "pills"},
            ]},
        },
    }


def models_view() -> dict[str, Any]:
    """Return distinct receipt-artifact and fine-tuning populations."""
    return {
        "id": "ml-models", "name": "Models", "brick": "machine_learning",
        "icon": "🤖", "layout": {"type": "flex", "direction": "column"},
        "components": [
            _receipt_models(), finetuning_jobs(),
        ],
        "metadata": {
            "description": "Receipt artifacts and fine-tuning jobs",
            "nav_label": "Models", "nav_order": 52,
        },
    }


__all__ = ["models_view"]
