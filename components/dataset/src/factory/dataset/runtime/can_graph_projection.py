"""Public Dataset-owned projection of immutable CAN records through Graph MCP."""
from __future__ import annotations

from typing import Any

from .adapters.can_taxonomize import CanTaxonomizeStageAdapter
from .helpers import load_records_from_uri


def project_can_graph(dataset_uri: str, graph_backend: str = "") -> dict[str, Any]:
    records = load_records_from_uri(dataset_uri)
    projected = list(CanTaxonomizeStageAdapter(
        graph_backend=graph_backend or "persistent_networkx",
    ).execute(records, {"graph_backend": graph_backend}))
    node_ids = {node_id for record in projected
                for node_id in record.get("taxonomy_node_ids", [])}
    return {
        "status": "completed", "dataset_uri": dataset_uri,
        "record_count": len(projected), "entity_ids": sorted(node_ids),
        "entity_count": len(node_ids),
    }


__all__ = ["project_can_graph"]
