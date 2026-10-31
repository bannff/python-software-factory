"""Immutable document retry tests for the SQLite storage adapter."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from factory.storage.runtime.adapters.doc_sqlite import SQLiteDocumentStore
from factory.storage.runtime.adapters.doc_tinydb import TinyDBDocumentStore


def test_create_match_and_conflict_preserve_the_first_document(tmp_path) -> None:
    store = SQLiteDocumentStore(str(tmp_path / "docs.db"))
    first = {"content_hash": "sha256:a", "value": "first"}
    assert store.create_or_match("eval_results", "eval-r1", first, "sha256:a").status == "created"
    assert store.create_or_match("eval_results", "eval-r1", first, "sha256:a").status == "matched"
    conflict = store.create_or_match(
        "eval_results", "eval-r1", {"content_hash": "sha256:b", "value": "second"}, "sha256:b",
    )
    assert conflict.status == "conflict"
    assert store.get("eval_results", "eval-r1").data == first


def test_concurrent_divergent_retries_accept_only_one_payload(tmp_path) -> None:
    store = SQLiteDocumentStore(str(tmp_path / "docs.db"))

    def write(value: str) -> str:
        return store.create_or_match(
            "eval_results", "eval-race", {"content_hash": f"sha256:{value}", "value": value},
            f"sha256:{value}",
        ).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(write, ("a", "b")))
    assert sorted(statuses) == ["conflict", "created"]
    assert store.get("eval_results", "eval-race").data["value"] in {"a", "b"}


def test_tinydb_create_match_and_conflict_preserve_the_first_document(tmp_path) -> None:
    pytest.importorskip("tinydb")
    store = TinyDBDocumentStore(str(tmp_path / "docs.json"))
    first = {"content_hash": "sha256:a", "value": "first"}
    assert store.create_or_match("eval_results", "eval-r1", first, "sha256:a").status == "created"
    assert store.create_or_match("eval_results", "eval-r1", first, "sha256:a").status == "matched"
    conflict = store.create_or_match(
        "eval_results", "eval-r1", {"content_hash": "sha256:b", "value": "second"}, "sha256:b",
    )
    assert conflict.status == "conflict"
    assert store.get("eval_results", "eval-r1").data == first
