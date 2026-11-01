"""Health must not present a collection-wide count as the caller's own (#28).

The deployment reported ``5 memories`` from health while every read tool
returned 0: health counted the whole collection, reads were scoped to the
caller's principal. Both numbers are now reported, each labelled.
"""
from __future__ import annotations

import tempfile

import pytest

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _stores():
    yield "memory", lambda: InMemoryStore()
    chromadb = pytest.importorskip("chromadb")
    assert chromadb
    from factory.memory.runtime.adapters.amem import AMemStore
    yield "amem", lambda: AMemStore(storage_path=tempfile.mkdtemp(), llm_complete=None)


@pytest.mark.parametrize("make", [make for _, make in _stores()], ids=[name for name, _ in _stores()])
def test_health_reports_collection_and_caller_scopes_that_match_the_read_path(make) -> None:
    rt = MemoryRuntime(store=make())
    rt.store(user_id="kiro-agent", content="a")
    rt.store(user_id="kiro-agent", content="b")
    rt.store(user_id="local-operator", content="c")

    mine = rt.health_check("local-operator")
    assert mine.details["collection_count"] == 3
    assert mine.details["principal_count"] == len(rt.list_all("local-operator")) == 1
    assert mine.details["user_id"] == "local-operator"
    assert "3 in the collection" in mine.message and "1 for 'local-operator'" in mine.message

    nobody = rt.health_check("someone-else")
    assert nobody.details["principal_count"] == len(rt.list_all("someone-else")) == 0
    assert nobody.details["collection_count"] == 3


def test_health_without_a_principal_reports_only_the_collection() -> None:
    rt = MemoryRuntime(store=InMemoryStore())
    rt.store(user_id="u1", content="a")
    health = rt.health_check()
    assert health.details["collection_count"] == 1
    assert "principal_count" not in health.details


def test_health_tool_scopes_to_the_ambient_principal() -> None:
    import asyncio

    from factory.mcp_utils.interface import reset_envelope, set_envelope
    from factory.memory.server import create_mcp_server

    rt = MemoryRuntime(store=InMemoryStore())
    rt.store(user_id="kiro-agent", content="a")
    rt.store(user_id="local-operator", content="b")
    tools = {tool.name: tool for tool in asyncio.run(create_mcp_server(rt).list_tools())}
    token = set_envelope({"tenant_id": "t", "principal_id": "local-operator"})
    try:
        result = tools["health_check"].fn()
    finally:
        reset_envelope(token)
    assert result.ok
    assert result.data.details["collection_count"] == 2
    assert result.data.details["principal_count"] == 1
