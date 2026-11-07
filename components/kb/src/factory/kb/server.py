"""FastMCP server interface exposing KB tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .runtime.runtime import KBRuntime
from .runtime.vector_store_selection import configure_remote_store, configure_vector_store
from .authoring import KBAuthoring
from .mcp import tools, resources, prompts
from factory.mcp_utils.server import make_lazy_runner

logger = logging.getLogger(__name__)

def _surface(runtime: KBRuntime | None = None) -> tuple[KBRuntime, KBAuthoring, Path]:
    config_dir = Path(os.environ.get("KB_CONFIG_DIR", "./config"))
    if runtime is None:
        runtime = KBRuntime.from_config_dir(config_dir)
        configure_vector_store(runtime)
        configure_remote_store(runtime)
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
