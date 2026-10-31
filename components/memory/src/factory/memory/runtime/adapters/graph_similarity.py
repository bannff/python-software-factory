"""Near-duplicate memory linking via persisted embedding vectors.

Split out of ``graph_store.py`` to keep that file under the 200 LOC ceiling.
Gate A.5 `6edab2de` P1-latent fix retained: the vector is embedded ONCE per
``store()`` call and persisted as a node property (``embed_vector``), so
comparing against every peer reads their already-stored vectors instead of
re-embedding all of them from scratch each time — O(n) reads, not O(n)
fresh model calls, per write.
"""
from __future__ import annotations

import uuid

from factory.graph.interface import GraphRuntime, Relationship
from factory.memory.runtime.embedding_local import LlamaCppEmbedder

_SIMILARITY_THRESHOLD = 0.85


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def link_similar(
    graph: GraphRuntime, embedder: LlamaCppEmbedder,
    memory_id: str, content: str, user_id: str,
) -> None:
    """Link near-duplicate memories via a persisted embedding vector."""
    if not embedder.is_semantic:
        return
    [vector] = embedder.embed([content])
    memory = graph.get_entity(memory_id)
    if memory is not None:
        memory.properties["embed_vector"] = vector
        graph.update_entity(memory)
    peers = graph.find_entities(entity_type="memory", properties={"user_id": user_id}, limit=200)
    for peer in peers:
        if peer.id == memory_id:
            continue
        peer_vector = peer.properties.get("embed_vector")
        if not peer_vector or cosine(vector, peer_vector) < _SIMILARITY_THRESHOLD:
            continue
        graph.add_relationship(Relationship(
            id=str(uuid.uuid4()), type="similar_to", source_id=memory_id, target_id=peer.id,
        ))


def recall_path(graph: GraphRuntime, memory_id: str, entity_to_memory) -> dict:
    """The real graph neighborhood that surfaced this memory (row 45's
    recall inspection, owner direction 2026-09-16): who owns it, what it
    followed, and which peers it is ``similar_to`` — with a real cosine
    score recomputed from the persisted vectors (not fabricated), same
    threshold ``store()`` itself uses. Returns an empty neighborhood
    (never raises) when ``memory_id`` doesn't exist."""
    memory = graph.get_entity(memory_id)
    if memory is None:
        return {"owner_id": None, "followed": None, "similar": []}
    owners = graph.get_neighbors(memory_id, relationship_type="HAS_MEMORY", direction="in", limit=1)
    predecessors = graph.get_neighbors(memory_id, relationship_type="FOLLOWED_BY", direction="in", limit=1)
    peers = graph.get_neighbors(memory_id, relationship_type="similar_to", direction="out", limit=20)
    vector = memory.properties.get("embed_vector")
    similar = []
    for peer in peers:
        peer_vector = peer.properties.get("embed_vector")
        score = cosine(vector, peer_vector) if vector and peer_vector else None
        similar.append({"memory": entity_to_memory(peer), "score": score})
    similar.sort(key=lambda item: item["score"] or 0.0, reverse=True)
    return {
        "owner_id": owners[0].properties.get("user_id") if owners else None,
        "followed": entity_to_memory(predecessors[0]) if predecessors else None,
        "similar": similar,
    }


__all__ = ["cosine", "link_similar", "recall_path"]
