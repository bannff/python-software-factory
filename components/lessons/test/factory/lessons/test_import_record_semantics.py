"""Lessons migration import persistence and merge-semantics tests."""
from __future__ import annotations

import asyncio

import pytest

from factory.lessons.server import create_mcp_server

from .test_import_record import (
    _ADAPTER, _RECORD, _data, _import, _runtime, _values,
)

def test_import_lands_as_user_authored_accepted(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    result = asyncio.run(_import(mcp, _values(evidence=("kirocrew-1",))))
    data = _data(result)
    assert data["imported"] is True and data["replayed"] is False
    assert data["outcome"] == "inserted"
    lesson = data["lesson"]
    assert lesson["status"] == "accepted"
    assert lesson["source"] == "user_explicit"
    assert lesson["confidence"] == 1.0
    assert lesson["source_ref"] == f"{_ADAPTER}:{_RECORD}"
    assert lesson["evidence"] == ["kirocrew-1"]


def test_exact_replay_is_idempotent(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    values = _values()
    first = _data(asyncio.run(_import(mcp, values)))
    second = _data(asyncio.run(_import(mcp, values)))
    assert first["imported"] is True
    assert second["replayed"] is True and second["imported"] is False
    assert second["outcome"] == "unchanged"
    assert first["lesson"]["lesson_id"] == second["lesson"]["lesson_id"]
    assert len(runtime.lifecycle.list("tenant", "owner")) == 1


def test_enrichment_merges_without_deleting_stored_clause(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    base = _data(asyncio.run(_import(
        mcp, _values(negative="Never invent a source", evidence=("first",)),
    )))
    enriched = _data(asyncio.run(_import(
        mcp, _values(rule="  always cite the exact source ", evidence=("second",)),
    )))
    assert base["outcome"] == "inserted"
    assert enriched["outcome"] == "enriched" and enriched["imported"] is True
    lesson = enriched["lesson"]
    assert lesson["lesson_id"] == base["lesson"]["lesson_id"]
    assert lesson["negative"] == "Never invent a source"
    assert lesson["evidence"] == ["first", "second"]


def test_owner_isolation_produces_distinct_records(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    mine = _data(asyncio.run(_import(mcp, _values(owner_id="owner"))))
    theirs = _data(asyncio.run(_import(mcp, _values(owner_id="other"))))
    assert mine["lesson"]["lesson_id"] != theirs["lesson"]["lesson_id"]
    assert runtime.lifecycle.get(
        "tenant", "owner", mine["lesson"]["lesson_id"],
    ).owner_id == "owner"
    assert runtime.lifecycle.store.get(
        "tenant", "owner", theirs["lesson"]["lesson_id"],
    ) is None


def test_repo_scope_separates_identity(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    glob = _data(asyncio.run(_import(mcp, _values())))
    scoped = _data(asyncio.run(_import(mcp, _values(repo_scope="acme/widgets"))))
    other = _data(asyncio.run(_import(mcp, _values(repo_scope="acme/gadgets"))))
    ids = {glob["lesson"]["lesson_id"], scoped["lesson"]["lesson_id"],
           other["lesson"]["lesson_id"]}
    assert len(ids) == 3
    assert scoped["lesson"]["scope"] == "persona"
    assert scoped["lesson"]["scope_id"] == "acme/widgets"


def test_non_lessons_kind_is_refused_by_dto() -> None:
    from factory.lessons.mcp.contracts import ImportLessonInput

    with pytest.raises(Exception):
        ImportLessonInput.model_validate({**_values(), "kind": "memory"})


def test_strict_extra_field_is_rejected() -> None:
    from factory.lessons.mcp.contracts import ImportLessonInput

    with pytest.raises(Exception):
        ImportLessonInput.model_validate({**_values(), "surprise": "x"})
