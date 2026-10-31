"""Deterministic admission policy for Dataset recipe stages."""
from __future__ import annotations

from .contracts import DatasetRecipe

RETAINED_STAGE_NAMES = frozenset({
    "local-validate",
    "scenario_generate",
    "context_ingest",
    "context_correlate",
    "context_augment",
    "can_ingest",
    "csv_can_ingest",
    "can_profile",
    "can_prior_policy",
    "can_signal_schema",
    "can_synthesize",
    "can_window",
    "can_window_v2",
    "can_augment",
    "can_taxonomize",
})


def admit_recipe(recipe: DatasetRecipe) -> DatasetRecipe:
    """Reject any recipe stage that Dataset cannot deterministically materialize."""
    disallowed = sorted({stage.name for stage in recipe.stages} - RETAINED_STAGE_NAMES)
    if disallowed:
        raise ValueError(
            f"Disallowed dataset recipe stages: {', '.join(disallowed)}"
        )
    return recipe
