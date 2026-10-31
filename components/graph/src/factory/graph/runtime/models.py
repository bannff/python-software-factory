"""Pydantic models for the graph brick runtime.

Holds caller-supplied data contracts that don't belong on
``ports.Protocol`` (the Protocol stays adapter-shape only). Today the
only resident is :class:`TaxonomyEdgeSpec`, which lets typed reads
walk arbitrary one-hop taxonomy edges without the graph brick
encoding any domain-specific labels.

Tracked under bd python-factory-ecph9 (epic python-factory-hadbi
domain-agnostic Companion-X). Meta-architect verdict
``9a4aba3c-d076-48a9-9499-5e24b0931a35`` and strands-expert verdict
``9b6d46cd-ed23-4a32-b3a0-40479b845768``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TaxonomyEdgeSpec(BaseModel):
    """Per-call taxonomy join spec for typed graph reads.

    Each spec describes a single out-direction relationship from
    Finding to a taxonomy node. The adapter walks the edge once per
    Finding and copies a fixed set of neighbor properties into named
    row columns. Missing edges yield ``None`` for every declared
    column, so consumers see a consistent row shape.

    Example — security agent (preserves today's row keys verbatim)::

        TaxonomyEdgeSpec(
            relationship_type="CLASSIFIED_AS",
            target_label="CWECategory",
            target_props={"cwe_id": "cwe_id", "name": "cwe_name"},
        )
        TaxonomyEdgeSpec(
            relationship_type="CONFORMS_TO",
            target_label="OCSFEventClass",
            target_props={
                "class_uid": "ocsf_uid", "class_name": "ocsf_class",
            },
        )

    A future wine-domain agent could pass::

        TaxonomyEdgeSpec(
            relationship_type="TASTED_AS",
            target_label="Varietal",
            target_props={"id": "varietal_id", "name": "varietal_name"},
        )

    Attributes:
        relationship_type: Outbound edge label, e.g. ``CLASSIFIED_AS``.
        target_label: Neighbor node label to match, e.g. ``CWECategory``.
        target_props: ``{neighbor_property: row_column_name}`` mapping;
            the keys live on the matched neighbor node, the values are
            the flat-row keys the typed reads project.
    """

    relationship_type: str
    target_label: str
    target_props: dict[str, str]

    model_config = ConfigDict(extra="forbid")


__all__ = ["TaxonomyEdgeSpec"]
