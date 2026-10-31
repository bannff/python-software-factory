"""Adapter-shared taxonomy helpers for typed Finding reads.

The graph brick's typed reads accept a caller-supplied
:class:`TaxonomyEdgeSpec` list (bd python-factory-ecph9 / epic
python-factory-hadbi domain-agnostic Companion-X). When the caller
passes ``None`` we fall back to the security CWE/OCSF defaults defined
here — adapter-local back-compat, NOT a Protocol contract default.

Both the networkx and Neo4j adapters import this module so the default
edges + the row-projection contract stay in one place.
"""

from __future__ import annotations

from ..models import TaxonomyEdgeSpec


# Legacy security defaults preserved verbatim (cwe_id / cwe_name /
# ocsf_class / ocsf_uid row column names match pre-ecph9 behavior).
_DEFAULT_SECURITY_EDGES: tuple[TaxonomyEdgeSpec, ...] = (
    TaxonomyEdgeSpec(
        relationship_type="CLASSIFIED_AS", target_label="CWECategory",
        target_props={"cwe_id": "cwe_id", "name": "cwe_name"},
    ),
    TaxonomyEdgeSpec(
        relationship_type="CONFORMS_TO", target_label="OCSFEventClass",
        target_props={"class_uid": "ocsf_uid", "class_name": "ocsf_class"},
    ),
)


def resolve_edges(
    edges: list[TaxonomyEdgeSpec] | None,
) -> tuple[TaxonomyEdgeSpec, ...]:
    """``None`` -> adapter default; ``[]`` -> no taxonomy join."""
    return _DEFAULT_SECURITY_EDGES if edges is None else tuple(edges)


__all__ = ["TaxonomyEdgeSpec", "resolve_edges", "_DEFAULT_SECURITY_EDGES"]
