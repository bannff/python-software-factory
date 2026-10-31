"""Native metadata-filter push-down for Neo4j adapters.

bd:python-factory-b2d2o (epic python-factory-hadbi). Mirrors lin6p's
``test_tags_pushdown_neo4j`` shape for the generic ``metadata`` filter.
Pins:

* N9  ``metadata is None`` → no ``meta_<k>`` fragment, no params.
* N10 single key → ``m.meta_k = $meta_k`` and ``params["meta_k"]`` bound.
* N11 multiple keys → AND-joined.
* N12 ``tags + metadata`` → BOTH fragments present.
* N13 HNSW ``_vector_search`` gets the same metadata clauses.
* N14 Hypothesis: any safe key → ``m.meta_<k> = $meta_<k>``.

Mock the Neo4j driver/session — no live DB needed.
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
    from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
    driver, session = _mock_driver()
    with patch.object(Neo4jMemoryStore, "_ensure_constraints", lambda self: None), \
         patch("factory.memory.runtime.adapters.neo4j.GraphDatabase") as mock_gd:
        mock_gd.driver.return_value = driver
        store = Neo4jMemoryStore(uri="bolt://x", user="u", password="p", database="db")
    return store, session


def _build_embedding_store():
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
def _last_cypher(s: MagicMock) -> str:
    return s.run.call_args[0][0]


def _last_params(s: MagicMock) -> dict:
    return s.run.call_args[1]


# -- Neo4jMemoryStore.retrieve --


class TestNeo4jRetrieveMetadataPushdown:
    def test_metadata_none_uses_simple_cypher(self) -> None:
        """N9."""
        store, s = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u1", query="alpha"))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "meta_" not in cypher
        assert not any(k.startswith("meta_") for k in params)

    def test_metadata_empty_dict_short_circuits(self) -> None:
        """metadata={} is no-filter (asymmetric default)."""
        store, s = _build_neo4j_store()
        store.retrieve(MemoryQuery(user_id="u1", query="alpha", metadata={}))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "meta_" not in cypher
        assert not any(k.startswith("meta_") for k in params)

    def test_metadata_single_key_includes_filter(self) -> None:
        """N10."""
        store, s = _build_neo4j_store()
        store.retrieve(
            MemoryQuery(user_id="u1", query="alpha", metadata={"run_id": "r-1"}),
        )
        cypher, params = _last_cypher(s), _last_params(s)
        assert "m.meta_run_id = $meta_run_id" in cypher
        assert params["meta_run_id"] == "r-1"

    def test_metadata_multiple_keys_and_joined(self) -> None:
        """N11."""
        store, s = _build_neo4j_store()
        store.retrieve(MemoryQuery(
            user_id="u1", query="alpha",
            metadata={"run_id": "r-1", "agent_id": "a"},
        ))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "m.meta_run_id = $meta_run_id" in cypher
        assert "m.meta_agent_id = $meta_agent_id" in cypher
        assert params["meta_run_id"] == "r-1"
        assert params["meta_agent_id"] == "a"
    def test_combined_tags_and_metadata(self) -> None:
        """N12."""
        store, s = _build_neo4j_store()
        store.retrieve(MemoryQuery(
            user_id="u1", query="alpha",
            tags=["wine"], metadata={"run_id": "r-1"},
        ))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
        assert "m.meta_run_id = $meta_run_id" in cypher
        assert params["tags"] == ["wine"]
        assert params["meta_run_id"] == "r-1"
        # Existing param threading still works.
        assert params["uid"] == "u1"
        assert params["q"] == "alpha"
        assert params["lim"] == 5

# -- Neo4jEmbeddingMemoryStore._vector_search --


class TestNeo4jEmbeddingVectorSearchMetadataPushdown:
    def test_metadata_none_no_filter(self) -> None:
        store, s, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(user_id="u1", query="x"))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "meta_" not in cypher
        assert not any(k.startswith("meta_") for k in params)

    def test_metadata_set_includes_filter(self) -> None:
        """N13."""
        store, s, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(
            user_id="u1", query="x", metadata={"target_app": "billing"},
        ))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "m.meta_target_app = $meta_target_app" in cypher
        assert params["meta_target_app"] == "billing"

    def test_existing_where_clause_preserved_with_metadata_and_tags(
        self,
    ) -> None:
        """user_id + min_relevance + tags + metadata all coexist."""
        store, s, _b, _e = _build_embedding_store()
        store.retrieve(MemoryQuery(
            user_id="u1", query="x",
            tags=["wine"], metadata={"run_id": "r-1"},
        ))
        cypher, params = _last_cypher(s), _last_params(s)
        assert "m.user_id = $uid" in cypher
        assert "score >= $min_rel" in cypher
        assert "ANY(t IN m.tags WHERE t IN $tags)" in cypher
        assert "m.meta_run_id = $meta_run_id" in cypher
        assert params["tags"] == ["wine"]
        assert params["meta_run_id"] == "r-1"


# -- N14 — Hypothesis fragment shape per safe key --


_SAFE_KEY = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    ),
    min_size=1, max_size=12,
).filter(lambda x: not x[0].isdigit())
_VAL = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
    min_size=1, max_size=12,
)


@settings(max_examples=30, deadline=None)
@given(key=_SAFE_KEY, value=_VAL)
def test_neo4j_pushdown_property_safe_key_shape(key: str, value: str) -> None:
    store, s = _build_neo4j_store()
    store.retrieve(MemoryQuery(user_id="u1", query="x", metadata={key: value}))
    cypher, params = _last_cypher(s), _last_params(s)
    assert f"m.meta_{key} = $meta_{key}" in cypher
    assert params[f"meta_{key}"] == value


@settings(max_examples=30, deadline=None)
@given(key=_SAFE_KEY, value=_VAL)
def test_embedding_pushdown_property_safe_key_shape(key: str, value: str) -> None:
    store, s, _b, _e = _build_embedding_store()
    store.retrieve(MemoryQuery(user_id="u1", query="x", metadata={key: value}))
    cypher, params = _last_cypher(s), _last_params(s)
    assert f"m.meta_{key} = $meta_{key}" in cypher
    assert params[f"meta_{key}"] == value
