"""Collision-safe node-attribute merging for the NetworkX adapter.

Kept in its own module so ``networkx_adapter.py`` stays <200 LOC.
"""

from __future__ import annotations

from typing import Any

from ..entity_contract import normalize_entity_properties
from ..ports import Entity


def node_attrs(entity: Entity) -> dict[str, Any]:
    """Merge canonical type/labels with caller properties, collision-safe.

    Canonical ``entity.type`` / ``entity.labels`` always own the ``type`` /
    ``labels`` node attributes. Reserved-key relocation is delegated to the
    shared, backend-agnostic ``normalize_entity_properties`` seam so NetworkX
    and Neo4j treat colliding caller keys identically. Building one flat dict
    removes any duplicate-kwarg crash on ``add_node``.
    """
    attrs = normalize_entity_properties(entity)
    attrs["type"] = entity.type
    attrs["labels"] = entity.labels
    return attrs
