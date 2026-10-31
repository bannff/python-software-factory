"""Backend-agnostic Entity property normalization (single source of truth).

``Entity.type`` and ``Entity.labels`` are canonical node attributes. Some
backends (NetworkX ``add_node(id, type=..., labels=...)``) splat those onto
the node as explicit kwargs, so a caller-supplied ``properties["type"]`` or
``properties["labels"]`` would collide. Rather than let one adapter crash and
another silently pass the raw key through, ALL adapters route through this one
relocation so the same ``Entity`` round-trips identically on every backend.

Reserved keys in ``properties`` are relocated to ``prop_<key>``:
  ``type``   -> ``prop_type``
  ``labels`` -> ``prop_labels``
Every other key is left untouched.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid a runtime import cycle with ports.py
    from .ports import Entity

logger = logging.getLogger(__name__)

# Caller-property keys that collide with canonical node attributes.
RESERVED_NODE_ATTRS: tuple[str, ...] = ("type", "labels")


def normalize_entity_properties(entity: "Entity") -> dict[str, Any]:
    """Return ``entity.properties`` with reserved keys relocated.

    Backend-agnostic and non-mutating: a fresh dict is returned. A caller
    value under a reserved key is preserved under ``prop_<key>`` (never lost)
    and logged at DEBUG. This is the ONLY place reserved-key handling lives;
    both the NetworkX and Neo4j adapters call it so a given ``Entity`` stores
    and reads back identical properties regardless of backend.
    """
    props: dict[str, Any] = dict(entity.properties)
    for reserved in RESERVED_NODE_ATTRS:
        if reserved in props:
            relocated = f"prop_{reserved}"
            logger.debug(
                "graph: caller property %r collides with reserved node "
                "attribute; relocating to %r", reserved, relocated,
            )
            props[relocated] = props.pop(reserved)
    return props
