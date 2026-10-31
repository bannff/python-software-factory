"""MCP server factory for memory brick."""

from __future__ import annotations

import os
from typing import Any

from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.mcp import (
    register_deterministic,
    register_operational,
    register_hybrid,
    register_temporal,
    register_prompts,
    register_resources,
    register_views,
    register_migration_import,
)
from factory.mcp_utils.server import make_lazy_runner


def _default_runtime() -> MemoryRuntime:
    """Create runtime with backend from config brick layered resolution."""
    from factory.mcp_utils.config_helpers import get_infra
    backend = get_infra("memory.backend", "memory")
    if backend == "neo4j":
        return _neo4j_runtime()
    if backend == "amem":
        return _amem_runtime()
    if backend == "graph":
        return _graph_runtime()
    return MemoryRuntime()


def _graph_runtime() -> MemoryRuntime:
    """Create the M7.7 unified-graph-memory runtime (persistent_networkx)."""
    from factory.memory.runtime.adapters.graph_store import GraphMemoryStore
    return MemoryRuntime(store=GraphMemoryStore())


def _neo4j_runtime() -> MemoryRuntime:
    """Create Neo4j runtime, optionally with semantic embeddings."""
    from factory.mcp_utils.config_helpers import get_infra, get_neo4j_config
    from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
    neo4j = get_neo4j_config()
    base = Neo4jMemoryStore(
        uri=neo4j["uri"],
        user=neo4j["user"],
        password=neo4j["password"],
        database=neo4j["database"],
    )
    embed = get_infra("memory.embeddings", "").lower()
    if embed in ("1", "true", "yes", "bedrock", "openai"):
        from factory.memory.runtime.embedding import LLMGatewayEmbedder
        from factory.memory.runtime.adapters.neo4j_embedding import Neo4jEmbeddingMemoryStore
        emb_backend = embed if embed in ("bedrock", "openai") else "bedrock"
        embedder = LLMGatewayEmbedder(backend=emb_backend)
        llm_complete = _get_llm_complete()
        store = Neo4jEmbeddingMemoryStore(base=base, embedder=embedder, llm_complete=llm_complete)
        return MemoryRuntime(store=store)
    return MemoryRuntime(store=base)


def _amem_runtime() -> MemoryRuntime:
    """Create A-MEM runtime with ChromaDB + LLM evolution."""
    from factory.memory.runtime.adapters.amem import AMemStore

    llm_complete = _get_llm_complete()
    store = AMemStore(llm_complete=llm_complete)
    return MemoryRuntime(store=store)


def _get_llm_complete():
    """Return the configured gateway completion callback for memory evolution.

    Resolves the SAME chat profile the agent uses (``COMPANION_X_CHAT_MODEL``,
    default ``openrouter``) via ``factory.llm_gateway.interface.resolve_chat_profile``
    + an official LangChain integration — NOT ``LLMRuntime().get_provider()``,
    whose ``FACTORY_LLM_ADAPTER`` default is ``bedrock`` regardless of what the
    product is actually configured for. That mismatch meant A-MEM content
    evolution silently required AWS credentials on an OpenRouter-configured
    deployment (P1 item 14, owner smoke #2 18:35) — memory evolution is an
    optional enrichment step, never a reason to depend on a provider the rest
    of the product doesn't use. ``AMEM_LLM_MODEL`` scopes an explicit model
    override to A-MEM only; leaving it unset uses the same model chat uses.
    """
    try:
        from factory.llm_gateway.interface import resolve_chat_profile

        from .runtime.adapters.langchain_completion import build_langchain_complete

        model_id = os.environ.get("AMEM_LLM_MODEL") or os.environ.get(
            "COMPANION_X_CHAT_MODEL", "openrouter",
        )
        resolve_chat_profile(model_id)  # fail fast on an unresolvable profile
        return build_langchain_complete(model_id)
    except Exception:
        return None


def create_tool_catalog(runtime: MemoryRuntime | None = None) -> Any:
    """Create the transport-neutral typed tool catalog for MCP v2."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    runtime = runtime or _default_runtime()
    catalog = ToolCatalog("memory-module")
    register_deterministic(catalog, runtime)
    register_operational(catalog, runtime)
    register_hybrid(catalog, runtime)
    register_temporal(catalog, runtime)
    register_migration_import(catalog, runtime)
    register_views(catalog)
    register_resources(catalog, runtime)
    register_prompts(catalog, runtime)
    return catalog


def create_mcp_server(runtime: MemoryRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for memory brick."""
    return {
        "name": "memory",
        "version": "1.0.0",
        "backends": ["memory", "mem0", "agentcore", "zep", "cognee", "neo4j", "amem", "graph"],
        "features": ["semantic_memory", "short_term_memory", "long_term_memory", "memory_consolidation", "graph_memory", "memory_evolution"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for memory brick."""
    return {"healthy": True, "backend": "memory"}


def describe_config_schema() -> dict[str, Any]:
    """Describe memory configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {"type": "string", "enum": ["memory", "mem0", "agentcore", "zep", "cognee", "neo4j", "amem", "graph"]},
            "max_memories": {"type": "integer", "description": "Max memories per agent"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
