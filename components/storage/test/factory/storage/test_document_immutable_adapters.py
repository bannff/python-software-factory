"""Fake-backed immutable-write contract tests for external document adapters."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from factory.storage.runtime.adapters.doc_mongodb import MongoDBDocumentStore
from factory.storage.runtime.adapters.doc_neo4j import Neo4jDocumentStore


class _MongoCollection:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def update_one(self, query: dict, update: dict, upsert: bool) -> SimpleNamespace:
        doc_id = query["_id"]
        if doc_id not in self.records:
            self.records[doc_id] = dict(update["$setOnInsert"])
            return SimpleNamespace(upserted_id=doc_id)
        return SimpleNamespace(upserted_id=None)

    def find_one(self, query: dict) -> dict[str, Any] | None:
        record = self.records.get(query["_id"])
        return dict(record) if record else None


class _MongoDatabase(dict[str, _MongoCollection]):
    def __missing__(self, collection: str) -> _MongoCollection:
        self[collection] = store = _MongoCollection()
        return store


class _Neo4jSession:
    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        self.nodes = nodes

    def run(self, query: str, **params: Any) -> SimpleNamespace:
        assert "MERGE (d:Document {id: $id})" in query
        doc_id, props = params["id"], params["props"]
        created = doc_id not in self.nodes
        if created:
            self.nodes[doc_id] = dict(props)
        return SimpleNamespace(single=lambda: {"d": self.nodes[doc_id], "created": created})

    def __enter__(self) -> "_Neo4jSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _Neo4jDriver:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}

    def session(self, **_: Any) -> _Neo4jSession:
        return _Neo4jSession(self.nodes)


def _mongo_store() -> tuple[MongoDBDocumentStore, _MongoDatabase]:
    database = _MongoDatabase()
    store = MongoDBDocumentStore.__new__(MongoDBDocumentStore)
    store._db = database
    return store, database


def _neo4j_store() -> tuple[Neo4jDocumentStore, _Neo4jDriver]:
    driver = _Neo4jDriver()
    store = Neo4jDocumentStore.__new__(Neo4jDocumentStore)
    store._driver, store._database = driver, "neo4j"
    return store, driver


def test_mongodb_create_or_match_preserves_first_document() -> None:
    store, database = _mongo_store()
    first = {"content_hash": "sha256:first", "value": "first"}
    assert store.create_or_match("runs", "r1", first, "sha256:first").status == "created"
    assert store.create_or_match("runs", "r1", first, "sha256:first").status == "matched"
    conflict = store.create_or_match(
        "runs", "r1", {"content_hash": "sha256:second", "value": "second"}, "sha256:second",
    )
    assert conflict.status == "conflict"
    assert database["runs"].records["r1"]["value"] == "first"


def test_neo4j_create_or_match_preserves_first_document() -> None:
    store, driver = _neo4j_store()
    first = {"content_hash": "sha256:first", "value": "first"}
    assert store.create_or_match("runs", "r1", first, "sha256:first").status == "created"
    assert store.create_or_match("runs", "r1", first, "sha256:first").status == "matched"
    conflict = store.create_or_match(
        "runs", "r1", {"content_hash": "sha256:second", "value": "second"}, "sha256:second",
    )
    assert conflict.status == "conflict"
    assert driver.nodes["r1"]["d_value"] == "first"
