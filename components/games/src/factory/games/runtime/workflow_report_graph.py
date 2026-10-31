"""Graph count queries for experiment reports.

Migrated off f-string Cypher (bd python-factory-ky0i) onto the typed
graph tools shipped in bd python-factory-j1lb. ``count_entities_by_run``
returns label-bucketed counts; verdict histograms now bucket
``get_findings_for_run`` rows in Python instead of asking Cypher to do it.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

# bd:python-factory-qer1z — security default; domains can override via count_labels arg.
_COUNT_LABELS = ("SuspectedVuln", "Finding", "ProvenExploit", "EndpointInventory")
DEFAULT_COUNT_LABELS: tuple[str, ...] = _COUNT_LABELS


def _typed_counts(
    invoker: Any, run_id: str, count_labels: Iterable[str] | None = None,
) -> dict[str, int]:
    """Return per-label counts for a run via the typed graph tool."""
    labels = tuple(count_labels) if count_labels is not None else DEFAULT_COUNT_LABELS
    if not labels:
        return {}
    try:
        r = invoker(
            "graph_graph_count_entities_by_run",
            run_id=run_id, labels=list(labels),
        )
        if not r or not r.ok or r.data is None:
            return {}
        return {key: int(value) for key, value in r.data.counts.items()}
    except Exception as e:
        logger.warning("graph_count_entities_by_run failed: %s", e)
        return {}


def _typed_verdicts(
    invoker: Any, run_id: str,
    taxonomy_edges: list[dict] | None = None,
) -> dict[str, int]:
    """Bucket Finding rows by ``verdict`` using the typed findings tool.

    ``taxonomy_edges`` is accepted for signature symmetry with the rest of
    the typed-graph callers (bd:python-factory-st587). The verdict
    histogram only reads ``verdict``, so callers who want to skip wasted
    taxonomy joins should pass ``taxonomy_edges=[]``; ``None`` keeps the
    back-compat CWE/OCSF default.
    """
    kwargs: dict[str, Any] = {"run_id": run_id, "app": "", "limit": 1000}
    if taxonomy_edges is not None:
        kwargs["taxonomy_edges"] = taxonomy_edges
    try:
        r = invoker("graph_graph_get_findings_for_run", **kwargs)
        if not r or not r.ok or r.data is None:
            return {}
        rows = r.data.rows
    except Exception as e:
        logger.warning("graph_get_findings_for_run failed: %s", e)
        return {}
    histogram: dict[str, int] = {}
    for row in rows:
        verdict = str(row.get("verdict", "unknown"))
        histogram[verdict] = histogram.get(verdict, 0) + 1
    return histogram


def _typed_endpoints_total(invoker: Any, run_id: str) -> int:
    """Return ``EndpointInventory.count`` for the latest inventory in the run."""
    try:
        r = invoker(
            "graph_graph_find_entities",
            entity_type="EndpointInventory",
            properties={"run_id": run_id}, limit=1,
        )
        if not r or not r.ok or r.data is None:
            return 0
        entities = r.data.entities
        if not entities:
            return 0
        return int(entities[0].properties.get("count", 0))
    except Exception as e:
        logger.warning("graph_find_entities(EndpointInventory) failed: %s", e)
        return 0


def graph_counts(
    invoker: Any, run_id: str,
    count_labels: Iterable[str] | None = None,
    taxonomy_edges: list[dict] | None = None,
) -> dict[str, Any]:
    """Fetch ground-truth counts from graph for this run.

    ``count_labels`` overrides the default 4-label security tuple
    (bd:python-factory-qer1z) so future domain agents can drive the same
    counter without touching engine code.

    ``taxonomy_edges`` (bd:python-factory-st587) forwards into the typed
    Finding query that powers the verdict histogram. The label-counts
    query (``_typed_counts``) and endpoint lookup (``_typed_endpoints_total``)
    do not read taxonomy columns, so they ignore the kwarg.
    """
    if count_labels is not None and not tuple(count_labels):
        return {
            "suspected_vuln_count": 0,
            "finding_count": 0,
            "finding_verdicts": {},
            "proven_exploit_count": 0,
            "endpoints_discovered": 0,
        }
    counts = _typed_counts(invoker, run_id, count_labels)
    verdicts = _typed_verdicts(invoker, run_id, taxonomy_edges=taxonomy_edges)
    return {
        "suspected_vuln_count": counts.get("SuspectedVuln", 0),
        "finding_count": counts.get("Finding", 0),
        "finding_verdicts": verdicts,
        "proven_exploit_count": counts.get("ProvenExploit", 0),
        "endpoints_discovered": _typed_endpoints_total(invoker, run_id),
    }
