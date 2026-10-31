"""Memory supersession over the shared graph (row 47 substrate).

Owner ruling 2026-09-16 06:32: the curator (A-MEM evolution today, the
similarity job later) replaces memories — never a user-facing restore
action. Old memory stays in the graph (never deleted); a ``superseded_by``
edge plus a ``_status=superseded`` property drop it out of default
retrieval (``retrieve()``, ``list_all()``, ``stats()`` in ``graph_store.py``
— compx-auditor `8f718ea5` P1: the first cut only excluded it from
``retrieve()``) while keeping it queryable for the memory detail view's
history. ``_status`` (not ``meta_`` prefixed) so it can never collide with
caller-supplied ``metadata={"status": ...}`` (compx-auditor `8f718ea5` P2).

Split out of ``graph_store.py`` to keep that file under the 200 LOC ceiling
(same doctrine as the earlier Portability security-test split this
session) — free functions over the graph runtime, not a second class,
since ``GraphMemoryStore`` is still the one ``MemoryStore`` adapter.
"""
from __future__ import annotations

import uuid

from factory.graph.interface import Entity, GraphRuntime, Relationship
from factory.memory.runtime.models import Memory


def supersede(graph: GraphRuntime, old_id: str, new_id: str) -> bool:
    """Mark ``old_id`` replaced by ``new_id``. Returns ``False`` (no write)
    if either id doesn't exist, or if they belong to different users — a
    cross-user chain would let ``history()`` (unscoped, like ``get()``/
    ``delete()``) leak another user's memory content (compx-auditor
    `8f718ea5` P2). No partial edge is ever written on any rejection.

    Idempotency/fan-in are disclosed known gaps, not fixed (compx-auditor
    `8f718ea5` P2): calling this twice on the same pair writes two distinct
    ``superseded_by`` edges (harmless for ``history()``, which dedupes via
    ``get_neighbors``'s set, but will pollute the row-51 graph visualizer
    once it exists); two different ``old_id``s superseded by the same
    ``new_id`` (fan-in) makes ``history()``'s single-predecessor walk pick
    one branch deterministically-but-arbitrarily. Both are inert today
    since there is no caller — revisit when the curator trigger lands.
    """
    old_entity = graph.get_entity(old_id)
    new_entity = graph.get_entity(new_id)
    if old_entity is None or new_entity is None:
        return False
    if old_entity.properties.get("user_id") != new_entity.properties.get("user_id"):
        return False
    old_entity.properties["_status"] = "superseded"
    graph.update_entity(old_entity)
    graph.add_relationship(Relationship(
        id=str(uuid.uuid4()), type="superseded_by", source_id=old_id, target_id=new_id,
    ))
    return True


def history(
    graph: GraphRuntime, memory_id: str, entity_to_memory: "callable[[Entity], Memory]",
) -> list[Memory]:
    """Every version of the chain containing ``memory_id``, newest first —
    the data the memory detail view's history section reads.

    Walks FORWARD to the chain head first (compx-auditor `8f718ea5` P2: a
    backward-only walk called on a non-head id silently omitted newer
    versions, contradicting this function's own "every version" contract),
    then walks the full chain backward from there.

    ``direction="in"``/``"out"``: a predecessor points ``superseded_by`` AT
    the current node (edge incoming from the predecessor's side); the
    successor is the target of the current node's own outgoing edge.
    """
    head = graph.get_entity(memory_id)
    seen_forward: set[str] = set()
    while head is not None and head.id not in seen_forward:
        seen_forward.add(head.id)
        successors = graph.get_neighbors(
            head.id, relationship_type="superseded_by", direction="out", limit=1,
        )
        if not successors:
            break
        head = successors[0]
    chain: list[Memory] = []
    current = head
    seen_backward: set[str] = set()
    while current is not None and current.id not in seen_backward:
        seen_backward.add(current.id)
        chain.append(entity_to_memory(current))
        predecessors = graph.get_neighbors(
            current.id, relationship_type="superseded_by", direction="in", limit=1,
        )
        current = predecessors[0] if predecessors else None
    return chain


__all__ = ["supersede", "history"]
