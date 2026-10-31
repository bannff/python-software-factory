"""Row 50 Embeddings status tool + the Gate A.5 `6edab2de` stats-scoping fix.

Split out of ``test_typed_mcp_boundary.py`` to keep that file under the
200-line ceiling (Guardian caught the overage — see tasks.md cycle 27).
"""
from __future__ import annotations

import asyncio

from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server


def _tools() -> dict[str, object]:
    server = create_mcp_server(MemoryRuntime())
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_embedding_status_reports_non_graph_backend_honestly() -> None:
    tools = _tools()
    result = tools["memory_get_embedding_status"].fn()
    assert result.ok
    assert result.data.is_graph_backend is False
    assert result.data.embedder_configured is False
    assert result.data.load_error == "not_graph_backend"
    assert "MEMORY_BACKEND=graph" in result.data.change_hint


def test_embedding_status_reports_graph_backend_with_fallback_embedder() -> None:
    from factory.graph.interface import GraphRuntime
    from factory.memory.runtime.adapters.graph_store import GraphMemoryStore
    from factory.memory.runtime.embedding_local import LlamaCppEmbedder
    store = GraphMemoryStore(runtime=GraphRuntime(), embedder=LlamaCppEmbedder(model_path=""), backend="networkx")
    tools = {t.name: t for t in asyncio.run(create_mcp_server(MemoryRuntime(store=store)).list_tools())}
    result = tools["memory_get_embedding_status"].fn()
    assert result.ok
    assert result.data.is_graph_backend is True
    assert result.data.embedder_configured is True
    assert result.data.is_semantic is False
    assert result.data.load_error == "model_file_not_found"


def test_embedding_status_reports_semantic_when_embedder_is_real() -> None:
    from factory.graph.interface import GraphRuntime
    from factory.memory.runtime.adapters.graph_store import GraphMemoryStore

    class FakeSemanticEmbedder:
        is_semantic = True
        load_error = None
        model_path = "/fake/model.gguf"
        dimensions = 4

        def embed(self, texts):
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    store = GraphMemoryStore(runtime=GraphRuntime(), embedder=FakeSemanticEmbedder(), backend="networkx")
    tools = {t.name: t for t in asyncio.run(create_mcp_server(MemoryRuntime(store=store)).list_tools())}
    result = tools["memory_get_embedding_status"].fn()
    assert result.ok
    assert result.data.is_semantic is True
    assert result.data.dimensions == 4


def test_memory_stats_scopes_to_caller_by_default_not_global_aggregate() -> None:
    """Gate A.5 `6edab2de` P1-latent fix: an omitted user_id must not
    silently return every user's counts once ambient identity resolves."""
    tools = _tools()
    tools["memory_store"].fn(content="mine", user_id="u")
    tools["memory_store"].fn(content="other person's", user_id="someone-else")
    scoped = tools["memory_stats"].fn(user_id="u")
    assert scoped.ok and scoped.data.total_memories == 1
    explicit_global = tools["memory_stats"].fn(user_id=None)
    # No ambient identity in this unit test -> falls through to the
    # pre-existing global-aggregate contract, unchanged for that case.
    assert explicit_global.ok and explicit_global.data.total_memories == 2
