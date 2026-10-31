"""Cypher composition helpers for typed Finding reads.

Pulled out of :mod:`neo4j_runs` to keep that module under the 200-LOC
ceiling once ``taxonomy_edges`` parameterisation landed (bd
python-factory-ecph9). Both builders are pure-string and have no
Neo4j-driver coupling.
"""

from __future__ import annotations

from ._taxonomy import TaxonomyEdgeSpec

# Static finding columns (no taxonomy join). Domain-aware columns are
# appended dynamically per-call from ``TaxonomyEdgeSpec.target_props``.
_FINDING_BASE_RETURN = (
    "f.id AS id, f.title AS title, f.description AS description, "
    "f.severity AS severity, f.location AS location, "
    "f.remediation AS remediation, f.cwe AS cwe, f.evidence AS evidence, "
    "f.verdict AS verdict, f.run_id AS run_id, f.app AS app, "
    "f.affected_resource_arn AS affected_resource_arn, "
    "f.finding_type AS finding_type, f.category AS category, "
    "f.created_at AS created_at, f.file AS file, "
    "f.function AS function, f.line_start AS line_start, "
    "f.line_end AS line_end, f.agent_id AS agent_id, "
    "f.vuln_class AS vuln_class, "
    # Verification oracle state (neutral; bd python-factory-216ti Contract B).
    "f.state AS state, "
    # Human-as-labeler grade (domain-neutral; written by either cockpit).
    "f.human_verdict AS human_verdict, f.graded_by AS graded_by, "
    "f.graded_at AS graded_at, f.graded_source AS graded_source"
)


def safe_label(label: str) -> str:
    """Strip non-alphanumerics; Cypher labels can't be parameterised."""
    return "".join(ch for ch in label if ch.isalnum() or ch == "_")


def build_taxonomy_clauses(
    edges: tuple[TaxonomyEdgeSpec, ...],
) -> tuple[str, str]:
    """Return ``(optional_matches, return_projection)`` for the edges.

    Positional alias ``e0``, ``e1`` ... so callers cannot smuggle Cypher
    into ``relationship_type`` or ``target_label``; both fields and
    every projection key/column are sanitised by :func:`safe_label`.
    """
    optionals: list[str] = []
    projections: list[str] = []
    for idx, edge in enumerate(edges):
        rel, label = safe_label(edge.relationship_type), safe_label(edge.target_label)
        if not rel or not label:
            continue
        alias = f"e{idx}"
        optionals.append(f"OPTIONAL MATCH (f)-[:{rel}]->({alias}:{label})")
        for prop, col in edge.target_props.items():
            sp, sc = safe_label(prop), safe_label(col)
            if sp and sc:
                projections.append(f"{alias}.{sp} AS {sc}")
    return " ".join(optionals), ", ".join(projections)


def finding_query(
    where_clause: str, edges: tuple[TaxonomyEdgeSpec, ...],
) -> str:
    """Compose Finding-read Cypher for the given filter + edges."""
    optionals, taxonomy_return = build_taxonomy_clauses(edges)
    return_fields = _FINDING_BASE_RETURN
    if taxonomy_return:
        return_fields = f"{return_fields}, {taxonomy_return}"
    return (
        f"MATCH (f:Finding) {where_clause}"
        f"{optionals + ' ' if optionals else ''}"
        f"RETURN {return_fields} ORDER BY f.created_at DESC LIMIT $limit"
    )


__all__ = ["safe_label", "build_taxonomy_clauses", "finding_query"]
