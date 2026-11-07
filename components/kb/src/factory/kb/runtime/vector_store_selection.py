"""Pick the KB vector-store backend from configuration.

Split out of ``server.py`` so the MCP surface stays a transport shell. Chroma
is a retired backend: it is reachable only when asked for by name, never as a
fallback, so a typo cannot silently re-enable it.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from .runtime import KBRuntime

logger = logging.getLogger(__name__)

_CHROMA_BACKENDS = frozenset({"chromadb", "chroma"})
_KNOWN_BACKENDS = frozenset({"neo4j", "graph", "bedrock"}) | _CHROMA_BACKENDS


def configure_vector_store(runtime: KBRuntime) -> None:
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
        elif kb_backend in _CHROMA_BACKENDS:
            _configure_chroma(runtime, get_infra)
        else:
            # Fail closed: an unknown value used to fall through to Chroma,
            # silently re-enabling a retired backend on a typo.
            raise ValueError(
                f"unsupported kb.backend {kb_backend!r}; expected one of "
                f"{', '.join(sorted(_KNOWN_BACKENDS))}"
            )
    except Exception as e:
        logger.error("KB vector store initialization failed: %s", e, exc_info=True)


def _configure_graph(runtime: KBRuntime) -> None:
    """M7.7 unified-graph-memory runtime (shared persistent_networkx)."""
    from .retrieval.graph import KBGraphVectorStore
    runtime.set_vector_store(KBGraphVectorStore())


def _configure_neo4j(runtime: KBRuntime, get_neo4j_config: Any) -> None:
    from .retrieval.neo4j_vector import Neo4jVectorStore, Neo4jVectorConfig
    from .retrieval.neo4j_embedding import LLMGatewayKBEmbedder, NoOpKBEmbedder

    neo4j = get_neo4j_config()
    try:
        embedder = LLMGatewayKBEmbedder()
        dims = embedder.dimensions
        if dims == 0:
            raise RuntimeError("no embedding provider reachable")
        logger.info("KB using LLMGatewayKBEmbedder (dims=%d)", dims)
    except Exception as e:
        logger.warning("KB embedder init failed, using NoOp: %s", e)
        embedder = NoOpKBEmbedder()
    cfg = Neo4jVectorConfig(
        uri=neo4j["uri"], user=neo4j["user"], password=neo4j["password"],
        embedding_dimensions=embedder.dimensions or 1024,
    )
    runtime.set_vector_store(Neo4jVectorStore(cfg, embedder=embedder))


def _configure_bedrock(runtime: KBRuntime, get_infra: Any) -> None:
    from .retrieval.bedrock import BedrockKBVectorStore, BedrockKBConfig

    kb_id = get_infra("kb.bedrock.kb_id", os.environ.get("KB_BEDROCK_KB_ID", ""))
    if not kb_id:
        from .retrieval.bedrock import _resolve_kb_id
        kb_id = _resolve_kb_id()
    region = get_infra("kb.bedrock.region", "us-east-1")
    cfg = BedrockKBConfig(kb_id=kb_id, region=region)
    runtime.set_vector_store(BedrockKBVectorStore(cfg))


def configure_remote_store(runtime: KBRuntime) -> None:
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
        from .retrieval.bedrock import BedrockKBVectorStore, BedrockKBConfig
        region = os.environ.get("KB_BEDROCK_REGION", "us-east-1")
        cfg = BedrockKBConfig(kb_id=kb_id, region=region)
        runtime.set_remote_store(BedrockKBVectorStore(cfg))
        logger.info("KB remote store configured: Bedrock KB %s", kb_id)
    except Exception as e:
        logger.debug("KB remote store init skipped: %s", e)


def _configure_chroma(runtime: KBRuntime, get_infra: Any) -> None:
    chroma_mode = get_infra("kb.chroma.mode", "embedded")
    if chroma_mode == "server":
        from .retrieval.chroma_server import ChromaServerVectorStore, ChromaServerConfig
        cfg = ChromaServerConfig(
            host=get_infra("kb.chroma.host", "localhost"),
            port=int(get_infra("kb.chroma.port", "8000")),
        )
        runtime.set_vector_store(ChromaServerVectorStore(cfg))
    else:
        from .retrieval.chroma import ChromaVectorStore, ChromaConfig
        chroma_dir = get_infra("kb.chroma.dir", "./chroma_data")
        runtime.set_vector_store(ChromaVectorStore(ChromaConfig(persist_directory=chroma_dir)))
