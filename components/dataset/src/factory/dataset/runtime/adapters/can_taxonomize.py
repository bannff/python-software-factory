"""CAN taxonomy wiring stage for the CAN failure-prediction pipeline.

Sits between ``can_ingest`` (or any later stage) and downstream
consumers. Reads canonical ``can_frame`` records, walks each one to
discover unique ``Vehicle`` / ``Trip`` / ``CANBus`` / ``ECU`` / ``Signal``
entities, materializes a ``Frame`` entity per record, and writes the
core taxonomy relationships into the graph brick's memory adapter
(persistent NetworkX by default).

The stage is **opt-in**: when ``enable_taxonomy`` is False the adapter
is a no-op pass-through that only adds an empty ``taxonomy_node_ids``
field to each record. That lets recipes opt into the wiring without
breaking existing pipelines.

Why batch writes?
    The graph brick's ``PersistentNetworkXGraph`` snapshots after every
    mutation, so issuing one ``add_entity`` per record would O(N) the
    disk. We collect unique entities in a single pass, then issue one
    mutation per *unique* node / relationship.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from ._can_taxonomize_builder import TaxonomyBuilder
from .mcp_graph_projection import (
    McpGraphProjectionAdapter, ObjectGraphProjectionAdapter,
)


class CanTaxonomizeStageAdapter:
    """Wire CAN frame records into the ``can_failure`` taxonomy graph.

    Implements ``DatasetStagePort`` so it slots into the recipe stage
    map. Defaults to ``persistent_networkx`` for offline / CI use; tests
    inject a fake graph via the ``graph`` kwarg.
    """

    name = "can_taxonomize"
    stage_version = "factory-can-taxonomize-1"
    allowed_config = frozenset({
        "enable_taxonomy", "graph_backend", "graph", "input_uri",
    })

    def __init__(
        self,
        *,
        graph=None,
        graph_backend: str = "persistent_networkx",
        projection=None,
    ) -> None:
        self._projection = projection or (
            ObjectGraphProjectionAdapter(graph) if graph is not None else None
        )
        self._graph_backend = graph_backend

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every record, tagged with its taxonomy node ids."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported can_taxonomize configuration: {sorted(unknown)}"
            )

        # Pass-through when taxonomy wiring is disabled — yields records
        # unchanged so downstream stages keep their contract.
        if not bool(values.get("enable_taxonomy", True)):
            for rec in records:
                yield _with_tag(rec, set())
            return

        projection = self._projection or McpGraphProjectionAdapter(
            backend=str(values.get("graph_backend", self._graph_backend)),
        )

        # Single streaming pass: discover entities + relationships
        # while tagging records, then commit in one batched write.
        builder = TaxonomyBuilder()
        materialised: list[dict[str, Any]] = []
        for rec in records:
            tag_ids = builder.absorb(rec)
            materialised.append(_with_tag(rec, tag_ids))

        builder.commit(projection)
        yield from materialised


def _with_tag(record: Any, tag_ids: set[str]) -> dict[str, Any]:
    """Return a copy of ``record`` with a ``taxonomy_node_ids`` list."""
    out = dict(record) if isinstance(record, dict) else {"value": record}
    out["taxonomy_node_ids"] = sorted(tag_ids)
    return out
