"""Helpers for :mod:`deterministic_typed`.

Pulled out so the registration module stays under 200 LOC after
``taxonomy_edges`` parameterisation landed (bd python-factory-ecph9).
"""

from __future__ import annotations

from typing import Any

from ..runtime.models import TaxonomyEdgeSpec


# Legacy security label set. Kept here as a back-compat default for the
# CURRENT typed-counts callers (rewards handler, evals trace summary,
# next-dashboard hooks). Domain-aware callers MUST pass ``labels=[...]``;
# Phase 4 will surface label config via the games-side workflow config
# so the security default can finally be retired.
_DEFAULT_COUNT_LABELS: tuple[str, ...] = (
    "SuspectedVuln", "Finding", "ProvenExploit",
    "EndpointInventory", "TargetApp",
)


def coerce_edges(
    raw: list[dict] | list[TaxonomyEdgeSpec] | None,
) -> list[TaxonomyEdgeSpec] | None:
    """Validate FE-supplied dicts; ``None`` flows through to the adapter."""
    if raw is None:
        return None
    return [
        e if isinstance(e, TaxonomyEdgeSpec) else TaxonomyEdgeSpec.model_validate(e)
        for e in raw
    ]


def coerce_labels(
    labels: list[str] | str | None,
) -> list[str]:
    """Tolerate JSON-string or comma-separated input; default to security set.

    Existing behavior — the security pipeline historically passes a
    list, the evals payload has passed JSON, and an early FE smoke
    sent comma-separated strings.
    """
    if isinstance(labels, str):
        import json as _json
        try:
            labels = _json.loads(labels)
        except (ValueError, TypeError):
            labels = [s.strip() for s in labels.split(",") if s.strip()]
    return list(labels) if labels else list(_DEFAULT_COUNT_LABELS)


def resolve_target_app(graph: Any, run_id: str) -> str:
    """Best-effort target-app resolution from typed reads (legacy default)."""
    for label in ("EndpointInventory", "SuspectedVuln", "Finding"):
        ents = graph.find_entities(label, {"run_id": run_id}, 1)
        if ents:
            app = str(ents[0].properties.get("app", ""))
            if app:
                return app
    return ""


__all__ = [
    "_DEFAULT_COUNT_LABELS", "coerce_edges",
    "coerce_labels", "resolve_target_app",
]
