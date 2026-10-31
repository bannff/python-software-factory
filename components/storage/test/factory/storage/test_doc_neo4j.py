"""Tests for Neo4jDocumentStore adapter.

Verifies CRUD operations against a mock Neo4j driver, with focus on
the delete() fix (python-factory-c5e): WITH/count before DETACH DELETE
so the returned count is accurate.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _FakeSession:
    """Mock Neo4j session backed by an in-memory dict of nodes."""

    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        self._nodes = nodes

    def run(self, cypher: str, **params: Any) -> Any:
        if "CONSTRAINT" in cypher:
            return MagicMock()
        if "CREATE (d:Document" in cypher:
            props = params.get("props", {})
            self._nodes[props.get("id", "")] = dict(props)
            return MagicMock()
        if "DETACH DELETE" in cypher:
            return self._delete(params)
        if "SET d +=" in cypher:
            return self._update(params)
        if "RETURN d" in cypher:
            return self._get(params)
        if "count(d) AS c" in cypher:
            return self._count(params)
        return MagicMock(single=lambda: None)

    def _delete(self, p: Any) -> Any:
        key, col = p.get("id", ""), p.get("col", "")
        existed = key in self._nodes and self._nodes[key].get("collection") == col
        if existed:
            del self._nodes[key]
        rec = MagicMock()
        rec.__getitem__ = lambda _, k: 1 if existed else 0
        return MagicMock(single=lambda: rec)

    def _update(self, p: Any) -> Any:
        key, col = p.get("id", ""), p.get("col", "")
        if key in self._nodes and self._nodes[key].get("collection") == col:
            self._nodes[key].update(p.get("props", {}))
            rec = MagicMock()
            rec.__getitem__ = lambda _, k: self._nodes[key]
            return MagicMock(single=lambda: rec)
        return MagicMock(single=lambda: None)

    def _get(self, p: Any) -> Any:
        key, col = p.get("id", ""), p.get("col", "")
        if key in self._nodes and self._nodes[key].get("collection") == col:
            rec = MagicMock()
            rec.__getitem__ = lambda _, k: self._nodes[key]
            return MagicMock(single=lambda: rec)
        return MagicMock(single=lambda: None)

    def _count(self, p: Any) -> Any:
        col = p.get("col", "")
        c = sum(1 for n in self._nodes.values() if n.get("collection") == col)
        rec = MagicMock()
        rec.__getitem__ = lambda _, k: c
        return MagicMock(single=lambda: rec)

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *a: Any) -> None:
        pass


def _make_store() -> Any:
    """Build a Neo4jDocumentStore bypassing __init__ (no real Neo4j)."""
    from factory.storage.runtime.adapters.doc_neo4j import Neo4jDocumentStore

    nodes: dict[str, dict[str, Any]] = {}
    driver = MagicMock()
    driver.session.return_value = _FakeSession(nodes)

    store = Neo4jDocumentStore.__new__(Neo4jDocumentStore)
    store._driver = driver
    store._database = "neo4j"
    store._uri = "bolt://localhost:7687"
    return store


# ---------------------------------------------------------------------------
# Tests — delete() behavior (the fix under test)
# ---------------------------------------------------------------------------


class TestNeo4jDelete:
    """Tests for delete() — the DETACH DELETE count fix."""

    @pytest.fixture
    def store(self) -> Any:
        return _make_store()

    def test_delete_existing_returns_true(self, store: Any) -> None:
        """delete() returns True when the document exists."""
        store.insert("notes", {"title": "hello"}, doc_id="d1")
        assert store.delete("notes", "d1") is True

    def test_delete_nonexistent_returns_false(self, store: Any) -> None:
        """delete() returns False when the document does not exist."""
        assert store.delete("notes", "ghost") is False

    def test_delete_wrong_collection_returns_false(self, store: Any) -> None:
        """delete() returns False when doc exists in a different collection."""
        store.insert("notes", {"title": "hello"}, doc_id="d1")
        assert store.delete("other", "d1") is False

    def test_delete_then_get_returns_none(self, store: Any) -> None:
        """After delete(), get() returns None."""
        store.insert("notes", {"title": "hello"}, doc_id="d1")
        store.delete("notes", "d1")
        assert store.get("notes", "d1") is None

    def test_delete_idempotent(self, store: Any) -> None:
        """Second delete() on same doc returns False."""
        store.insert("notes", {"title": "hello"}, doc_id="d1")
        assert store.delete("notes", "d1") is True
        assert store.delete("notes", "d1") is False

    def test_delete_single_returns_none(self, store: Any) -> None:
        """delete() returns False when session.run().single() is None."""
        with patch.object(store, "_driver") as drv:
            sess = MagicMock()
            drv.session.return_value.__enter__ = lambda s: sess
            drv.session.return_value.__exit__ = MagicMock(return_value=False)
            sess.run.return_value.single.return_value = None
            assert store.delete("notes", "d1") is False


# ---------------------------------------------------------------------------
# Tests — other CRUD operations (basic coverage)
# ---------------------------------------------------------------------------


class TestNeo4jCRUD:
    """Basic CRUD tests for Neo4jDocumentStore."""

    @pytest.fixture
    def store(self) -> Any:
        return _make_store()

    def test_insert_returns_document(self, store: Any) -> None:
        """insert() returns a Document with correct fields."""
        doc = store.insert("users", {"name": "Alice"}, doc_id="u1")
        assert doc.id == "u1"
        assert doc.collection == "users"

    def test_insert_generates_id(self, store: Any) -> None:
        """insert() generates a UUID when doc_id is None."""
        doc = store.insert("users", {"name": "Bob"})
        assert len(doc.id) > 0

    def test_get_existing(self, store: Any) -> None:
        """get() returns the document when it exists."""
        store.insert("users", {"name": "Alice"}, doc_id="u1")
        doc = store.get("users", "u1")
        assert doc is not None
        assert doc.id == "u1"

    def test_get_nonexistent(self, store: Any) -> None:
        """get() returns None for a missing document."""
        assert store.get("users", "ghost") is None

    def test_update_existing(self, store: Any) -> None:
        """update() returns updated document when it exists."""
        store.insert("users", {"name": "Alice"}, doc_id="u1")
        updated = store.update("users", "u1", {"name": "Alicia"})
        assert updated is not None

    def test_update_nonexistent(self, store: Any) -> None:
        """update() returns None for a missing document."""
        assert store.update("users", "ghost", {"name": "Nobody"}) is None
