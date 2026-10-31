"""Property-based tests for Neo4jVectorStore using Hypothesis.

Verifies CRUD and search invariants against a mock Neo4j driver.
Properties tested:
  - add then get roundtrip preserves document
  - add then delete then get returns None
  - delete of non-existent returns False
  - backfill with NoOpEmbedder returns 0
  - search always returns a list (never crashes)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.kb.runtime.models import Document
from factory.kb.runtime.retrieval.neo4j_embedding import NoOpKBEmbedder
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorConfig, Neo4jVectorStore

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_id = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_content = st.text(min_size=0, max_size=200)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

_EMBED_DIM = 4


class _FixedEmbedder:
    """Returns a deterministic fixed-dimension vector for every text."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * _EMBED_DIM for _ in texts]

    @property
    def dimensions(self) -> int:
        return _EMBED_DIM


class _FakeNeo4jStore:
    """In-memory node store backing the mock Neo4j session."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}

    def run(self, cypher: str, **params: Any) -> list[Any]:
        if "MERGE" in cypher or "SET" in cypher:
            return self._handle_merge(params)
        if "DETACH DELETE" in cypher:
            return self._handle_delete(params)
        if "RETURN n" in cypher and "WHERE" not in cypher:
            return self._handle_get(params)
        return []

    def _handle_merge(self, params: Any) -> list[Any]:
        doc_id = params.get("id")
        props = params.get("props")
        vec = params.get("vec")
        if props:
            self.nodes.setdefault(doc_id, {}).update(props)
        if vec is not None:
            self.nodes.setdefault(doc_id, {})["embedding"] = vec
        return []

    def _handle_delete(self, params: Any) -> list[Any]:
        doc_id = params.get("id")
        existed = doc_id in self.nodes
        self.nodes.pop(doc_id, None)
        rec = MagicMock()
        rec.__getitem__ = lambda _, k: 1 if existed else 0
        return [rec]

    def _handle_get(self, params: Any) -> list[Any]:
        doc_id = params.get("id")
        if doc_id not in self.nodes:
            return []
        rec = MagicMock()
        rec.__getitem__ = lambda _, k: self.nodes[doc_id] if k == "n" else None
        return [rec]


def _make_store(embedder: Any | None = None) -> Neo4jVectorStore:
    """Build a Neo4jVectorStore with a fully mocked driver."""
    fake = _FakeNeo4jStore()
    session = MagicMock()
    session.run = lambda cypher, **kw: fake.run(cypher, **kw)
    session.__enter__ = lambda s: s
    session.__exit__ = MagicMock(return_value=False)

    driver = MagicMock()
    driver.session.return_value = session

    with patch("factory.kb.runtime.retrieval.neo4j_vector.GraphDatabase") as mock_gd:
        mock_gd.driver.return_value = driver
        cfg = Neo4jVectorConfig(embed_on_ingest=embedder is not _NoOpSentinel)
        store = Neo4jVectorStore(config=cfg, embedder=embedder or NoOpKBEmbedder())
    # Re-bind driver so subsequent calls use the same mock
    store._driver = driver
    return store


_NoOpSentinel = object()


def _doc(doc_id: str, content: str = "") -> Document:
    return Document(id=doc_id, content=content)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id, content=_content)
def test_add_then_get_roundtrip(doc_id: str, content: str) -> None:
    """Storing then retrieving a document preserves id and content."""
    store = _make_store(_FixedEmbedder())
    store.add(_doc(doc_id, content))
    got = store.get(doc_id)
    assert got is not None, f"get({doc_id!r}) returned None after add"
    assert got.id == doc_id
    assert got.content == content


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id, content=_content)
def test_add_delete_then_get_returns_none(doc_id: str, content: str) -> None:
    """After add + delete, get returns None."""
    store = _make_store()
    store.add(_doc(doc_id, content))
    store.delete(doc_id)
    assert store.get(doc_id) is None


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id)
def test_delete_nonexistent_returns_false(doc_id: str) -> None:
    """Deleting a document that was never added returns False."""
    store = _make_store()
    assert store.delete(doc_id) is False


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id, content=_content)
def test_delete_existing_returns_true(doc_id: str, content: str) -> None:
    """Deleting a stored document returns True."""
    store = _make_store()
    store.add(_doc(doc_id, content))
    assert store.delete(doc_id) is True


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id, content=_content)
def test_backfill_with_noop_embedder_returns_zero(doc_id: str, content: str) -> None:
    """backfill_embeddings returns 0 when embedder has zero dimensions."""
    store = _make_store(NoOpKBEmbedder())
    store.add(_doc(doc_id, content))
    assert store.backfill_embeddings() == 0


@settings(max_examples=50, deadline=None)
@given(query=_content)
def test_search_always_returns_list(query: str) -> None:
    """search() never raises — always returns a (possibly empty) list."""
    store = _make_store()
    result = store.search(query, limit=5)
    assert isinstance(result, list)


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id)
def test_get_missing_returns_none(doc_id: str) -> None:
    """Getting a never-added document returns None."""
    store = _make_store()
    assert store.get(doc_id) is None


@settings(max_examples=50, deadline=None)
@given(doc_id=_safe_id, content_a=_content, content_b=_content)
def test_add_twice_last_write_wins(doc_id: str, content_a: str, content_b: str) -> None:
    """Adding the same id twice keeps the last content."""
    store = _make_store()
    store.add(_doc(doc_id, content_a))
    store.add(_doc(doc_id, content_b))
    got = store.get(doc_id)
    assert got is not None
    assert got.content == content_b, "last write should win"
