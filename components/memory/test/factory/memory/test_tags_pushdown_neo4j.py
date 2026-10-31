"""Native tags-filter push-down for Neo4j adapters.

bd:python-factory-26e2a (epic python-factory-hadbi). Pins the Cypher
WHERE-clause shape so:

* ``query.tags is None`` → no ``$tags`` binding, no ``ANY(t IN m.tags ...)``
  fragment in the cypher (back-compat with pre-lin6p callers).
* ``query.tags == []`` → also no native push-down (runtime post-filter
  short-circuits to ``[]``; we do not burn a Cypher round-trip).
* ``query.tags == [...]`` (non-empty) → cypher MUST include
  ``ANY(t IN m.tags WHERE t IN $tags)`` and the ``$tags`` param MUST be
  bound to the caller's list.

Mock the Neo4j driver/session — no live database needed. Runtime
post-filter at ``MemoryRuntime.retrieve`` stays in place as
defense-in-depth + tier 2/3 fallback (zep, cognee, mem0).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.memory.runtime.models import MemoryQuery


def _mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    session.run.return_value = []
    return driver, session


def _build_neo4j_store():
    """Build a Neo4jMemoryStore with a mocked driver — no live DB."""
    from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
    driver, session = _mock_driver()
    with patch.object(Neo4jMemoryStore, "_ensure_constraints", lambda self: None), \
         patch("factory.memory.runtime.adapters.neo4j.GraphDatabase") as mock_gd:
        mock_gd.driver.return_value = driver
        store = Neo4jMemoryStore(uri="bolt://x", user="u", password="p", database="db")
    return store, session


def _build_embedding_store():
    """Build a Neo4jEmbeddingMemoryStore with mocked base + embedder."""
    from factory.memory.runtime.adapters.neo4j_embedding import (
        Neo4jEmbeddingMemoryStore,
    )
    driver, session = _mock_driver()
    base = MagicMock()
    base.driver = driver
    base.database = "db"
    embedder = MagicMock()
    embedder.dimensions = 384
    embedder.embed.return_value = [[0.1] * 384]
    store = Neo4jEmbeddingMemoryStore(base=base, embedder=embedder)
    return store, session, base, embedder


def _last_cypher(session: MagicMock) -> str:
    return session.run.call_args[0][0]


def _last_params(session: MagicMock) -> dict:
    return session.run.call_args[1]


# -- Neo4jMemoryStore.retrieve --


class TestNeo4jRetrieveTagsPushdown:
    def test_neo4j_retrieve_tags_none_uses_simple_cypher(self) -> None:
        store, session = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u1", query="alpha"))
        cypher, params = _last_cypher(session), _last_params(session)
        assert "$tags" not in cypher
        assert "ANY(t IN" not in cypher
        assert "tags" not in params

    def test_neo4j_retrieve_tags_empty_short_circuits(self) -> None:
        """tags=[] does NOT add an empty $tags binding (runtime post-filter
        short-circuits to [] anyway — we don't pay the round-trip)."""
        store, session = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u1", query="alpha", tags=[]))
        cypher, params = _last_cypher(session), _last_params(session)
        assert "$tags" not in cypher
        assert "ANY(t IN" not in cypher
        assert "tags" not in params

    def test_neo4j_retrieve_tags_set_includes_tags_filter(self) -> None:
        store, session = _build_neo4j_store()
        store.retrieve(
            MemoryQuery(user_id="u1", query="alpha", tags=["wine-pairing-learnings"]),
        )
        cypher, params = _last_cypher(session), _last_params(session)
        assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
        assert params.get("tags") == ["wine-pairing-learnings"]

    def test_neo4j_retrieve_tags_multiple_threaded_through(self) -> None:
        store, session = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u1", query="x", tags=["a", "b", "c"]))
        assert _last_params(session)["tags"] == ["a", "b", "c"]

    def test_neo4j_retrieve_user_id_and_query_still_threaded(self) -> None:
        """Tags push-down does not break existing param threading."""
        store, session = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u-42", query="zeta", tags=["x"]))
        params = _last_params(session)
        assert params["uid"] == "u-42"
        assert params["q"] == "zeta"
        assert params["lim"] == 5  # default


# -- Neo4jEmbeddingMemoryStore._vector_search --


class TestNeo4jEmbeddingVectorSearchTagsPushdown:
    def test_embedding_retrieve_tags_none_no_filter(self) -> None:
        store, session, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(user_id="u1", query="x"))
        cypher, params = _last_cypher(session), _last_params(session)
        assert "$tags" not in cypher
        assert "ANY(t IN" not in cypher
        assert "tags" not in params

    def test_embedding_retrieve_tags_set_includes_filter(self) -> None:
        store, session, _b, _e = _build_embedding_store()
        store.retrieve(
            MemoryQuery(user_id="u1", query="x", tags=["security-learnings"]),
        )
        cypher, params = _last_cypher(session), _last_params(session)
        assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
        assert params["tags"] == ["security-learnings"]

    def test_embedding_retrieve_tags_empty_no_filter(self) -> None:
        store, session, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(user_id="u1", query="x", tags=[]))
        cypher, params = _last_cypher(session), _last_params(session)
        assert "$tags" not in cypher
        assert "tags" not in params

    def test_embedding_retrieve_existing_where_clause_preserved(self) -> None:
        """user_id + min_relevance must still be in the WHERE clause."""
        store, session, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(user_id="u1", query="x", tags=["a"]))
        cypher = _last_cypher(session)
        assert "m.user_id = $uid" in cypher
        assert "score >= $min_rel" in cypher


# -- Hypothesis property: non-empty tags → filter always present --


_TAG_ALPHABET = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
    ),
    min_size=1, max_size=12,
)


@settings(max_examples=30, deadline=None)
@given(tags=st.lists(_TAG_ALPHABET, min_size=1, max_size=5))
def test_neo4j_pushdown_property_non_empty_always_filters(tags: list[str]) -> None:
    store, session = _build_neo4j_store()
    store.retrieve(MemoryQuery(user_id="u1", query="x", tags=tags))
    cypher, params = _last_cypher(session), _last_params(session)
    assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
    assert params["tags"] == tags


@settings(max_examples=30, deadline=None)
@given(tags=st.lists(_TAG_ALPHABET, min_size=1, max_size=5))
def test_neo4j_embedding_pushdown_property_non_empty_always_filters(
    tags: list[str],
) -> None:
    store, session, _b, _e = _build_embedding_store()
    store.retrieve(MemoryQuery(user_id="u1", query="x", tags=tags))
    cypher, params = _last_cypher(session), _last_params(session)
    assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
    assert params["tags"] == tags
