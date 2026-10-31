"""MCP-layer tests for whole-graph export/import (row 48, owner direction
2026-09-16: "simple export/import of the whole graph to one file").

Paged (fixed 2026-09-16): a real graph exceeds the 16 MiB typed-egress cap
when inlined as one base64 blob, so export/import are paged — see
backup_models.py / backup.py module docstrings for the root-cause writeup.
These tests exercise the real paged flow end-to-end, including a
deliberately tiny per-test page size so a >1-page round trip is exercised
without needing a multi-megabyte fixture graph."""
from __future__ import annotations

import base64

import pytest

from factory.graph.mcp import backup as backup_module
from factory.graph.runtime.runtime import reset_runtime
from factory.graph.server import create_mcp_server


@pytest.fixture
def server():
    reset_runtime()
    yield create_mcp_server()
    reset_runtime()


async def _export_all_pages(server, backend: str = "networkx") -> tuple[bool, str, int]:
    """Page through graph_export and concatenate — mirrors the FE's loop."""
    export_tool = (await server.get_tool("graph_export")).fn
    chunks: list[str] = []
    page = 0
    page_count = 1
    while True:
        result = export_tool(backend=backend, page=page)
        assert result.ok is True
        if result.data.supported is False:
            return False, "", 0
        chunks.append(result.data.data_base64)
        page_count = result.data.page_count
        if result.data.done:
            break
        page += 1
    return True, "".join(chunks), page_count


async def _import_all_pages(server, data_base64: str, backend: str, page_chunk_chars: int) -> object:
    """Split data_base64 into pages and drive begin/page — mirrors the FE's loop."""
    begin_tool = (await server.get_tool("graph_import_begin")).fn
    page_tool = (await server.get_tool("graph_import_page")).fn
    total_pages = max(1, -(-len(data_base64) // page_chunk_chars))
    begin = begin_tool(backend=backend, total_pages=total_pages)
    assert begin.ok is True
    import_id = begin.data.import_id
    last = None
    for i in range(total_pages):
        chunk = data_base64[i * page_chunk_chars:(i + 1) * page_chunk_chars]
        last = page_tool(import_id=import_id, page=i, data_base64=chunk)
        assert last.ok is True
    return last


@pytest.mark.asyncio
async def test_export_then_import_round_trips_through_the_real_mcp_tools(server) -> None:
    add = (await server.get_tool("graph_add_entity")).fn
    add(entity_id="a", entity_type="memory", properties={"content": "alpha"}, backend="networkx")

    supported, data_base64, page_count = await _export_all_pages(server, backend="networkx")
    assert supported is True
    assert page_count == 1  # small fixture graph fits in one page at the real chunk size
    assert len(data_base64) > 0

    reset_runtime()
    backup_module._export_cache.clear()
    fresh = create_mcp_server()
    from factory.graph.mcp.backup_models import PAGE_CHUNK_CHARS
    imported = await _import_all_pages(fresh, data_base64, backend="networkx", page_chunk_chars=PAGE_CHUNK_CHARS)
    assert imported.data.imported is True

    fetched = (await fresh.get_tool("graph_get_entity")).fn(entity_id="a", backend="networkx")
    assert fetched.data.entity.properties["content"] == "alpha"


@pytest.mark.asyncio
async def test_export_pages_a_payload_larger_than_one_chunk(server, monkeypatch) -> None:
    # Force a tiny per-page size so this test proves real multi-page paging
    # without needing a multi-megabyte fixture graph.
    monkeypatch.setattr(backup_module, "PAGE_CHUNK_CHARS", 16)
    add = (await server.get_tool("graph_add_entity")).fn
    add(entity_id="a", entity_type="memory", properties={"content": "alpha-beta-gamma"}, backend="networkx")

    supported, data_base64, page_count = await _export_all_pages(server, backend="networkx")
    assert supported is True
    assert page_count > 1  # the tiny chunk size forces multiple pages
    assert len(data_base64) > 0


@pytest.mark.asyncio
async def test_import_page_rejects_an_unknown_import_id(server) -> None:
    page_tool = (await server.get_tool("graph_import_page")).fn
    result = page_tool(import_id="does-not-exist", page=0, data_base64="QQ==")
    assert result.ok is True
    assert result.data.imported is False
    assert result.data.error == "unknown_or_expired_import_id"


@pytest.mark.asyncio
async def test_import_rejects_a_corrupt_base64_payload(server) -> None:
    begin_tool = (await server.get_tool("graph_import_begin")).fn
    page_tool = (await server.get_tool("graph_import_page")).fn
    begin = begin_tool(backend="networkx", total_pages=1)
    result = page_tool(import_id=begin.data.import_id, page=0, data_base64="not-valid-base64!!!")
    assert result.ok is True
    assert result.data.imported is False
    assert result.data.error == "invalid_base64"


@pytest.mark.asyncio
async def test_import_rejects_a_well_formed_but_corrupt_snapshot(server) -> None:
    junk = base64.b64encode(b"not a real snapshot").decode("ascii")
    begin_tool = (await server.get_tool("graph_import_begin")).fn
    page_tool = (await server.get_tool("graph_import_page")).fn
    begin = begin_tool(backend="networkx", total_pages=1)
    result = page_tool(import_id=begin.data.import_id, page=0, data_base64=junk)
    assert result.ok is True
    assert result.data.imported is False
    assert result.data.error is not None


@pytest.mark.asyncio
async def test_export_reports_unsupported_on_the_neo4j_backend(server) -> None:
    result = (await server.get_tool("graph_export")).fn(backend="neo4j")
    assert result.ok is True
    assert result.data.supported is False
    assert result.data.byte_size == 0
