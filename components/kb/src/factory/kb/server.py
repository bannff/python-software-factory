"""FastMCP server interface exposing KB tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .runtime.runtime import KBRuntime
from .authoring import KBAuthoring
from .mcp import tools, resources, prompts
from factory.mcp_utils.server import make_lazy_runner

logger = logging.getLogger(__name__)


def _surface(runtime: KBRuntime | None = None) -> tuple[KBRuntime, KBAuthoring, Path]:
    config_dir = Path(os.environ.get("KB_CONFIG_DIR", "./config"))
    if runtime is None:
        runtime = KBRuntime.from_config_dir(config_dir)
        _configure_vector_store(runtime)
        _configure_remote_store(runtime)
    return runtime, KBAuthoring(config_dir), config_dir


def _register_tools(
    registry: Any, runtime: KBRuntime, authoring_mgr: KBAuthoring, config_dir: Path,
) -> None:
    tools.register_tools(
        registry, get_runtime=lambda: runtime, get_authoring=lambda: authoring_mgr,
        get_config_dir=lambda: config_dir,
    )


def create_tool_catalog(runtime: KBRuntime | None = None) -> Any:
    """Create the transport-neutral KB tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime, authoring_mgr, config_dir = _surface(runtime)
    catalog = ToolCatalog("kb-module")
    _register_tools(catalog, active_runtime, authoring_mgr, config_dir)
    resources.register(catalog, lambda: active_runtime, lambda: config_dir)
    prompts.register(catalog)
    return catalog


def create_mcp_server(runtime: KBRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def _configure_vector_store(runtime: KBRuntime) -> None:
    """Attempt to configure a vector store backend on the runtime.

    Tries config brick first (Neo4j / Chroma). If no config brick is
    available or initialization fails, logs an error — the runtime will
    raise on operations that require a vector store.
    """
    try:
        from factory.config.interface import get_infra, get_neo4j_config
    except ImportError:
        logger.error("KB: config brick unavailable — no vector store configured")
        return

    try:
        kb_backend = get_infra("kb.backend", "neo4j")
        if kb_backend == "bedrock":
            _configure_bedrock(runtime, get_infra)
        elif kb_backend == "neo4j":
            _configure_neo4j(runtime, get_neo4j_config)
        elif kb_backend == "graph":
            _configure_graph(runtime)
        else:
            _configure_chroma(runtime, get_infra)
    except Exception as e:
        logger.error("KB vector store initialization failed: %s", e, exc_info=True)


def _configure_graph(runtime: KBRuntime) -> None:
    """M7.7 unified-graph-memory runtime (shared persistent_networkx)."""
    from .runtime.retrieval.graph import KBGraphVectorStore
    runtime.set_vector_store(KBGraphVectorStore())


def _configure_neo4j(runtime: KBRuntime, get_neo4j_config: Any) -> None:
    from .runtime.retrieval.neo4j_vector import Neo4jVectorStore, Neo4jVectorConfig
    from .runtime.retrieval.neo4j_embedding import LLMGatewayKBEmbedder, NoOpKBEmbedder

    neo4j = get_neo4j_config()
    cfg = Neo4jVectorConfig(
        uri=neo4j["uri"], user=neo4j["user"], password=neo4j["password"],
    )
    try:
        embedder = LLMGatewayKBEmbedder()
        logger.info("KB using LLMGatewayKBEmbedder (dims=%d)", embedder.dimensions)
    except Exception as e:
        logger.warning("KB embedder init failed, using NoOp: %s", e)
        embedder = NoOpKBEmbedder()
    runtime.set_vector_store(Neo4jVectorStore(cfg, embedder=embedder))


def _configure_bedrock(runtime: KBRuntime, get_infra: Any) -> None:
    from .runtime.retrieval.bedrock import BedrockKBVectorStore, BedrockKBConfig

    kb_id = get_infra("kb.bedrock.kb_id", os.environ.get("KB_BEDROCK_KB_ID", ""))
    if not kb_id:
        from .runtime.retrieval.bedrock import _resolve_kb_id
        kb_id = _resolve_kb_id()
    region = get_infra("kb.bedrock.region", "us-east-1")
    cfg = BedrockKBConfig(kb_id=kb_id, region=region)
    runtime.set_vector_store(BedrockKBVectorStore(cfg))


def _configure_remote_store(runtime: KBRuntime) -> None:
    """Best-effort: attach Bedrock KB as remote store alongside primary.

    Runs independently of the primary backend. If KB_BEDROCK_KB_ID is set
    (or SSM param exists), the remote store is available via search_remote().
    Silent failure — the remote store is optional.
    """
    kb_id = os.environ.get("KB_BEDROCK_KB_ID", "")
    if not kb_id:
        try:
            from factory.config.interface import get_infra
            kb_id = get_infra("kb.bedrock.kb_id", "")
        except ImportError:
            pass
    if not kb_id:
        return  # No Bedrock KB configured — skip silently
    try:
        from .runtime.retrieval.bedrock import BedrockKBVectorStore, BedrockKBConfig
        region = os.environ.get("KB_BEDROCK_REGION", "us-east-1")
        cfg = BedrockKBConfig(kb_id=kb_id, region=region)
        runtime.set_remote_store(BedrockKBVectorStore(cfg))
        logger.info("KB remote store configured: Bedrock KB %s", kb_id)
    except Exception as e:
        logger.debug("KB remote store init skipped: %s", e)


def _configure_chroma(runtime: KBRuntime, get_infra: Any) -> None:
    chroma_mode = get_infra("kb.chroma.mode", "embedded")
    if chroma_mode == "server":
        from .runtime.retrieval.chroma_server import ChromaServerVectorStore, ChromaServerConfig
        cfg = ChromaServerConfig(
            host=get_infra("kb.chroma.host", "localhost"),
            port=int(get_infra("kb.chroma.port", "8000")),
        )
        runtime.set_vector_store(ChromaServerVectorStore(cfg))
    else:
        from .runtime.retrieval.chroma import ChromaVectorStore, ChromaConfig
        chroma_dir = get_infra("kb.chroma.dir", "./chroma_data")
        runtime.set_vector_store(ChromaVectorStore(ChromaConfig(persist_directory=chroma_dir)))


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for kb brick."""
    return {
        "name": "kb",
        "version": "1.0.0",
        "backends": ["chromadb_embedded", "chromadb_server", "neo4j", "bedrock", "graph"],
        "features": ["knowledge_base", "vector_search", "document_management", "semantic_search", "rag_support"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for kb brick."""
    try:
        config_dir = Path(os.environ.get("KB_CONFIG_DIR", "./config"))
        runtime = KBRuntime.from_config_dir(config_dir)
        return {"healthy": True, "collections": len(runtime.collections)}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def describe_config_schema() -> dict[str, Any]:
    """Describe kb configuration schema."""
    return {
        "type": "object",
        "properties": {
            "chroma_dir": {"type": "string", "description": "ChromaDB persist directory"},
            "embedding_model": {"type": "string", "description": "Embedding model to use"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
