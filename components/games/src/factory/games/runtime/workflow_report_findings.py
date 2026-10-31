"""Per-finding detail extraction from graph for experiment reports.

Migrated off f-string Cypher (bd python-factory-ky0i) onto the typed
graph tools shipped in bd python-factory-j1lb. The typed helpers
parameterize on Neo4j and return structured rows on networkx, so this
module no longer silently produces empty findings on local dev.

Per-finding row shapers live in
:mod:`workflow_report_finding_builders` so this file can stay under the
200 LOC ceiling once ``count_labels`` + ``taxonomy_edges`` thread
through (bd:python-factory-tmlrx + python-factory-st587).
"""
from __future__ import annotations

import logging
from typing import Any

from ._rl_stages import DEFAULT_COUNT_LABELS
from .workflow_report_finding_builders import _build_exploit_finding, _build_finding

__all__ = [
    "build_findings_detail",
    # Re-exported builders so legacy patch paths
    # ``factory.games.runtime.workflow_report_findings._build_finding``
    # / ``_build_exploit_finding`` keep resolving.
    "_build_finding",
    "_build_exploit_finding",
]

logger = logging.getLogger(__name__)


def _typed_findings(
    invoker: Any, run_id: str,
    taxonomy_edges: list[dict] | None = None,
) -> list[dict]:
    """Return Finding rows for a run via the typed graph tool.

    ``taxonomy_edges`` (bd:python-factory-st587) is forwarded into
    ``graph_graph_get_findings_for_run``. ``None`` keeps the CWE/OCSF
    security back-compat default; ``[]`` skips the taxonomy join entirely.
    """
    kwargs: dict[str, Any] = {"run_id": run_id, "app": "", "limit": 1000}
    if taxonomy_edges is not None:
        kwargs["taxonomy_edges"] = taxonomy_edges
    try:
        r = invoker("graph_graph_get_findings_for_run", **kwargs)
        if not r or not r.ok or r.data is None:
            return []
        return r.data.rows
    except Exception as e:
        logger.warning("graph_get_findings_for_run failed: %s", e)
        return []


def _typed_entities(invoker: Any, entity_type: str, run_id: str) -> list[dict]:
    """Return entity properties for a run via the typed graph tool."""
    try:
        r = invoker(
            "graph_graph_find_entities",
            entity_type=entity_type,
            properties={"run_id": run_id}, limit=1000,
        )
        if not r or not r.ok or r.data is None:
            return []
        return [entity.properties for entity in r.data.entities]
    except Exception as e:
        logger.warning("graph_find_entities(%s) failed: %s", entity_type, e)
        return []


def build_findings_detail(
    invoker: Any, run_id: str,
    count_labels: list[str] | None = None,
    taxonomy_edges: list[dict] | None = None,
) -> dict[str, Any]:
    """Query graph for full finding + exploit detail, return report sections.

    ``count_labels`` is a (primary, exploit) pair (bd:python-factory-qer1z); defaults
    to ``("Finding", "ProvenExploit")``. Primary slot must stay ``"Finding"`` — the
    column shape ``_build_finding`` reads is keyed to the typed-findings envelope.

    ``taxonomy_edges`` (bd:python-factory-st587) is forwarded to
    ``_typed_findings`` so domain agents can drive Cypher-shape via config.
    """
    labels = tuple(count_labels) if count_labels is not None else DEFAULT_COUNT_LABELS
    if not labels:
        return {
            "findings": [],
            "finding_categories": {},
            "dynamic_verification_summary": {},
        }
    exploit_label = labels[1] if len(labels) >= 2 else "ProvenExploit"
    findings_raw = _typed_findings(invoker, run_id, taxonomy_edges=taxonomy_edges)
    exploits_raw = _typed_entities(invoker, exploit_label, run_id)
    suspected_raw = _typed_entities(invoker, "SuspectedVuln", run_id)

    findings = [
        _build_finding(row, suspected_raw, exploits_raw)
        for row in findings_raw
    ]
    if not findings and exploits_raw:
        findings = [_build_exploit_finding(row) for row in exploits_raw]

    verdicts = [f.get("verdict", "unknown") for f in findings]
    dast_only = not findings_raw and exploits_raw
    categories = {
        "actionable_confirmed_verified": sum(1 for v in verdicts if v == "CONFIRMED"),
        "needs_review": sum(1 for v in verdicts if v == "NEEDS_REVIEW"),
        "safe_rejected": sum(1 for v in verdicts if v == "REJECTED"),
        "total_raw": len(exploits_raw) if dast_only else len(suspected_raw),
        "total_after_dedup": len(findings),
        "total_after_validation": sum(1 for v in verdicts if v == "CONFIRMED"),
    }
    has_sast = len(suspected_raw) > 0
    dv = {
        "verified_finding": len(exploits_raw),
        "verification_failed": 0,
        "not_tested": max(0, len(findings_raw) - len(exploits_raw)),
        "sast_predictions_confirmed": len(exploits_raw) if has_sast else 0,
        "sast_predictions_total": len(suspected_raw),
        "sast_correlation_rate": round(
            len(exploits_raw) / len(suspected_raw), 2) if has_sast else 0.0,
    }
    return {
        "findings": findings,
        "finding_categories": categories,
        "dynamic_verification_summary": dv,
    }
