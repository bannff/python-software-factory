"""Fine-tuning jobs component for the ML Models UIView.

Split from ``views_models.py`` to respect the <200 LOC tenet.
"""

from __future__ import annotations

from typing import Any


def finetuning_jobs() -> dict[str, Any]:
    """Fine-tuning jobs (LoRA/QLoRA/MLX) — the other half of 'all the ML'."""
    return {
        "id": "ml-finetuning-jobs",
        "type": "item_list",
        "props": {
            "data_tool": "ml_list_finetuning_jobs",
            "data_path": "$.jobs",
            "item_key": "id",
            "empty_icon": "cpu-chip",
            "empty_message": "No fine-tuning jobs yet.",
            "header": {
                "icon": "cpu-chip",
                "stats_tool": "ml_list_finetuning_jobs",
                "stats_map": {"jobs": "$.count"},
            },
            "item_layout": {
                "status_dot": {
                    "value_path": "$.status",
                    "states": {
                        "completed": "emerald", "running": "blue",
                        "failed": "red", "pending": "yellow",
                    },
                },
                "title": "$.base_model",
                "subtitle": "$.method",
                "badge": {"field": "status", "color_map": "item_layout.status_dot.states"},
                "value": {"path": "$.loss", "format": "number"},
            },
            "detail": {
                "metadata": [
                    {"label": "Method", "path": "$.method", "zone": "config"},
                    {"label": "Objective", "path": "$.training_objective", "zone": "config"},
                    {"label": "LoRA Rank", "path": "$.lora_rank", "zone": "config"},
                    {"label": "Learning Rate", "path": "$.learning_rate", "zone": "config"},
                    {"label": "Checkpoints", "path": "$.checkpoints", "zone": "identity"},
                    {"label": "Job ID", "path": "$.id", "render_as": "copy_id", "zone": "identity"},
                    {"label": "Error", "path": "$.error", "zone": "identity"},
                ],
                "tabs": [
                    {
                        "id": "checkpoints", "label": "Checkpoints",
                        "tool": "ml_list_checkpoints",
                        "args": {"job_id": "$.id"},
                        "data_path": "$.checkpoints",
                        "render_as": "list",
                    },
                ],
            },
        },
    }


__all__ = ["finetuning_jobs"]
