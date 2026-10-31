"""M7.7 Slice 1 — GraphMemoryStore: MemoryStore over the shared graph brick.

Runs against ``GraphRuntime.get_graph("networkx")`` (the plain, non-durable
backend) for fast hermetic isolation — the persistent/blob-store variant is
the ``graph`` brick's own concern and is exercised there, not re-tested here.
"""
from __future__ import annotations

from factory.graph.interface import GraphRuntime
from factory.memory.runtime.adapters.graph_store import GraphMemoryStore
from factory.memory.runtime.embedding_local import LlamaCppEmbedder
from factory.memory.runtime.models import MemoryQuery


def _store() -> GraphMemoryStore:
    return GraphMemoryStore(runtime=GraphRuntime(), embedder=LlamaCppEmbedder(model_path=""), backend="networkx")


def test_store_then_get_roundtrip() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="prefers dark mode", category="preference")
    fetched = store.get(memory.id)
    assert fetched is not None
    assert fetched.content == "prefers dark mode"
    assert fetched.user_id == "u1"
    assert fetched.category.value == "preference"


def test_list_all_scoped_to_user_and_ordered_newest_first() -> None:
    store = _store()
    store.store(user_id="u1", content="first")
    store.store(user_id="u1", content="second")
    store.store(user_id="u2", content="other user")
    listed = store.list_all("u1", limit=10)
    assert [m.content for m in listed] == ["second", "first"]


def test_retrieve_matches_substring_case_insensitively() -> None:
    store = _store()
    store.store(user_id="u1", content="Prefers Dark Mode")
    store.store(user_id="u1", content="unrelated content")
    hits = store.retrieve(MemoryQuery(user_id="u1", query="dark mode"))
    assert len(hits) == 1
    assert hits[0].content == "Prefers Dark Mode"


def test_update_corrects_content_in_place() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="prefers dark mode")
    updated = store.update(memory.id, "prefers light mode")
    assert updated is not None
    assert updated.content == "prefers light mode"
    assert updated.updated_at is not None
    refetched = store.get(memory.id)
    assert refetched is not None
    assert refetched.content == "prefers light mode"


def test_update_unknown_memory_returns_none() -> None:
    store = _store()
    assert store.update("nonexistent-id", "new content") is None


def test_delete_removes_the_memory() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="temp")
    assert store.delete(memory.id) is True
    assert store.get(memory.id) is None
    assert store.delete(memory.id) is False


def test_delete_user_memories_removes_all_and_only_that_user() -> None:
    store = _store()
    store.store(user_id="u1", content="a")
    store.store(user_id="u1", content="b")
    store.store(user_id="u2", content="c")
    deleted = store.delete_user_memories("u1")
    assert deleted == 2
    assert store.list_all("u1") == []
    assert len(store.list_all("u2")) == 1


def test_consolidate_promotes_short_term_to_long_term() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="fact", memory_type="short_term")
    promoted = store.consolidate("u1")
    assert promoted == 1
    assert store.get(memory.id).memory_type == "long_term"


def test_stats_counts_by_type_and_category_scoped_to_user() -> None:
    store = _store()
    store.store(user_id="u1", content="a", memory_type="short_term", category="fact")
    store.store(user_id="u1", content="b", memory_type="long_term", category="fact")
    store.store(user_id="u2", content="c")
    scoped = store.stats("u1")
    assert scoped.total_memories == 2
    assert scoped.by_type == {"short_term": 1, "long_term": 1}
    aggregate = store.stats()
    assert aggregate.total_memories == 3


def test_health_check_reports_graph_backend() -> None:
    health = _store().health_check()
    assert health.healthy is True
    assert health.backend == "graph"


def test_stores_create_a_has_memory_ownership_edge() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="a")
    owner = store._graph.get_entity("user:u1")
    assert owner is not None and owner.type == "user"
    neighbors = store._graph.get_neighbors("user:u1")
    assert any(n.id == memory.id for n in neighbors)


def test_semantic_similarity_links_near_duplicate_content() -> None:
    """When the embedder reports semantic mode, near-identical content links.

    Uses a canned deterministic vector pair via a tiny fake embedder rather
    than a real GGUF model (not available in this environment) — proves the
    ``_link_similar`` wiring, not the embedding model itself.
    """
    class FakeSemanticEmbedder:
        is_semantic = True

        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    store = GraphMemoryStore(runtime=GraphRuntime(), embedder=FakeSemanticEmbedder(), backend="networkx")
    first = store.store(user_id="u1", content="alpha")
    second = store.store(user_id="u1", content="alpha again")
    neighbors = store._graph.get_neighbors(second.id, relationship_type="similar_to")
    assert any(n.id == first.id for n in neighbors)


def test_supersede_creates_edge_and_marks_old_as_superseded() -> None:
    """Row 47 substrate — owner ruling 2026-09-16 06:32: the curator marks
    an old memory replaced, never a user restore action. Old node stays in
    the graph (never deleted) but drops out of default retrieval."""
    store = _store()
    old = store.store(user_id="u1", content="prefers light mode")
    new = store.store(user_id="u1", content="prefers dark mode")
    assert store.supersede(old.id, new.id) is True
    neighbors = store._graph.get_neighbors(new.id, relationship_type="superseded_by", direction="in")
    assert any(n.id == old.id for n in neighbors)
    assert store.get(old.id) is not None  # never deleted


def test_recall_path_reports_owner_chain_and_similar_peers_with_scores() -> None:
    """Row 45's recall inspection (owner direction 2026-09-16): the real
    owner/FOLLOWED_BY/similar_to edges around one memory, with a genuine
    recomputed cosine score — not a fabricated trace."""
    class FakeSemanticEmbedder:
        is_semantic = True

        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    store = GraphMemoryStore(runtime=GraphRuntime(), embedder=FakeSemanticEmbedder(), backend="networkx")
    first = store.store(user_id="u1", content="alpha")
    second = store.store(user_id="u1", content="alpha again")

    path = store.recall_path(second.id)

    assert path["owner_id"] == "u1"
    assert path["followed"] is not None and path["followed"].id == first.id
    assert len(path["similar"]) == 1
    assert path["similar"][0]["memory"].id == first.id
    assert path["similar"][0]["score"] == 1.0


def test_recall_path_on_a_nonexistent_memory_returns_an_empty_neighborhood() -> None:
    store = _store()
    path = store.recall_path("does-not-exist")
    assert path == {"owner_id": None, "followed": None, "similar": []}


def test_supersede_returns_false_for_unknown_ids_without_writing_a_partial_edge() -> None:
    store = _store()
    real = store.store(user_id="u1", content="real")
    assert store.supersede("nonexistent", real.id) is False
    assert store.supersede(real.id, "nonexistent") is False


def test_supersede_rejects_cross_user_pairs() -> None:
    """compx-auditor `8f718ea5` P2: a cross-user chain would let the
    unscoped history() walk leak another user's memory content."""
    store = _store()
    mine = store.store(user_id="u1", content="mine")
    theirs = store.store(user_id="u2", content="theirs")
    assert store.supersede(mine.id, theirs.id) is False
    assert store.supersede(theirs.id, mine.id) is False
    # neither write landed
    assert store._graph.get_neighbors(mine.id, relationship_type="superseded_by") == []
    assert store._graph.get_neighbors(theirs.id, relationship_type="superseded_by") == []


def test_superseded_memory_is_excluded_from_default_retrieve() -> None:
    store = _store()
    old = store.store(user_id="u1", content="dark mode preference v1")
    new = store.store(user_id="u1", content="dark mode preference v2")
    store.supersede(old.id, new.id)
    hits = store.retrieve(MemoryQuery(user_id="u1", query="dark mode"))
    assert [m.id for m in hits] == [new.id]


def test_superseded_memory_is_excluded_from_list_all() -> None:
    """compx-auditor `8f718ea5` P1: list_all is the surface the Memory tab's
    default list actually reads — retrieve()-only exclusion was a partial fix."""
    store = _store()
    old = store.store(user_id="u1", content="v1")
    new = store.store(user_id="u1", content="v2")
    store.supersede(old.id, new.id)
    listed = store.list_all("u1")
    assert [m.id for m in listed] == [new.id]


def test_superseded_memory_is_excluded_from_stats() -> None:
    store = _store()
    old = store.store(user_id="u1", content="v1")
    new = store.store(user_id="u1", content="v2")
    store.supersede(old.id, new.id)
    assert store.stats("u1").total_memories == 1


def test_history_walks_the_supersession_chain_newest_first() -> None:
    store = _store()
    v1 = store.store(user_id="u1", content="v1")
    v2 = store.store(user_id="u1", content="v2")
    v3 = store.store(user_id="u1", content="v3")
    store.supersede(v1.id, v2.id)
    store.supersede(v2.id, v3.id)
    chain = store.history(v3.id)
    assert [m.id for m in chain] == [v3.id, v2.id, v1.id]


def test_history_from_a_non_head_id_still_returns_the_full_chain() -> None:
    """compx-auditor `8f718ea5` P2: a backward-only walk called on a
    non-head id silently omitted newer versions — history() must walk
    forward to the head first regardless of which version id is passed."""
    store = _store()
    v1 = store.store(user_id="u1", content="v1")
    v2 = store.store(user_id="u1", content="v2")
    v3 = store.store(user_id="u1", content="v3")
    store.supersede(v1.id, v2.id)
    store.supersede(v2.id, v3.id)
    chain = store.history(v1.id)
    assert [m.id for m in chain] == [v3.id, v2.id, v1.id]


def test_history_of_a_never_superseded_memory_is_just_itself() -> None:
    store = _store()
    memory = store.store(user_id="u1", content="only version")
    assert [m.id for m in store.history(memory.id)] == [memory.id]
