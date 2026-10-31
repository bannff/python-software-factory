"""Typed deterministic MCP tools for the KB brick."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import Field

from factory.mcp_utils.interface import deterministic, ok
from factory.mcp_utils.runtime.tool_result import ToolResult

from ...models.surface import (
    KbCapabilitiesResult,
    KbCollectionRegistryResult,
    KbCollectionStatsRequest,
    KbCollectionStatsResult,
    KbConfigSchemaResult,
    KbEmptyRequest,
    KbHealthResult,
)
from ...runtime.collections import CollectionConfig
from ...runtime.envelope import ContextEnvelope
from ...runtime.models import Document, SearchResult


def register(
    mcp: Any,
    get_runtime: Callable[[], Any],
    get_authoring: Callable[[], Any],
    get_config_dir: Callable[[], Path],
) -> None:
    """Register typed deterministic KB tools."""

    @mcp.tool()
    @deterministic(input_model=KbEmptyRequest, output_model=KbCapabilitiesResult)
    def get_capabilities() -> ToolResult[KbCapabilitiesResult]:
        """Describe KB brick capabilities."""
        authoring_inst = get_authoring()
        try:
            from ...runtime.retrieval.chroma import CHROMADB_AVAILABLE
        except ImportError:
            chroma_available = False
        else:
            chroma_available = CHROMADB_AVAILABLE
        features = ["document_storage", "collections", "metadata_filtering"]
        try:
            vector_store = getattr(get_runtime(), "_vector_store", None)
            if vector_store is not None and "Neo4j" in type(vector_store).__name__:
                features.extend(["vector_search", "entity_extraction", "graph_rag"])
            elif chroma_available:
                features.append("vector_search")
            else:
                features.append("text_search")
        except Exception:
            features.append("vector_search" if chroma_available else "text_search")
        return ok(
            KbCapabilitiesResult(
                features=features,
                tooling={
                    "deterministic": [
                        "get_capabilities", "health_check", "describe_config_schema",
                        "get_collection_registry", "get_collection_stats",
                    ],
                    "operational": [
                        "ingest", "search", "get_document", "delete_document",
                        "list_documents",
                    ],
                    "authoring": [
                        "authoring.get_status", "authoring.validate_collections",
                        "authoring.upsert_collection", "authoring.delete_collection",
                    ],
                },
                details={
                    "authoring_enabled": authoring_inst.is_enabled(),
                    "chroma_available": chroma_available,
                    "config_dir": str(get_config_dir()),
                },
            )
        )

    @mcp.tool()
    @deterministic(input_model=KbEmptyRequest, output_model=KbHealthResult)
    def health_check() -> ToolResult[KbHealthResult]:
        """Run a fast health probe."""
        try:
            stats = get_runtime().get_collection_stats()
            return ok(KbHealthResult(status="ok", details={
                "document_count": stats.document_count,
                "config_dir": str(get_config_dir()),
            }))
        except Exception as exc:
            return ok(KbHealthResult(status="error", details={
                "error": f"{type(exc).__name__}: {exc}",
                "config_dir": str(get_config_dir()),
            }))

    @mcp.tool()
    @deterministic(input_model=KbEmptyRequest, output_model=KbConfigSchemaResult)
    def describe_config_schema() -> ToolResult[KbConfigSchemaResult]:
        """Describe configuration accepted by the KB brick."""
        config_schema: dict[str, Any] = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "KB_CONFIG_DIR": {"type": "string"},
                "KB_CHROMA_DIR": {"type": "string"},
                "KB_ENABLE_AUTHORING_TOOLS": {"type": "string"},
            },
        }
        return ok(KbConfigSchemaResult(
            config_schema=config_schema,
            domain_schemas={
                "document_schema": Document.model_json_schema(),
                "collection_schema": CollectionConfig.model_json_schema(),
                "envelope_schema": ContextEnvelope.model_json_schema(),
                "search_result_schema": SearchResult.model_json_schema(),
            },
        ))

    @mcp.tool()
    @deterministic(input_model=KbEmptyRequest, output_model=KbCollectionRegistryResult)
    def get_collection_registry() -> ToolResult[KbCollectionRegistryResult]:
        """Get all loaded collections."""
        collections = get_runtime().get_collection_registry().list_all()
        return ok(KbCollectionRegistryResult(
            collections=[{"id": item.id, "name": item.name} for item in collections],
            total=len(collections),
        ))

    @mcp.tool()
    @deterministic(
        input_model=KbCollectionStatsRequest,
        output_model=KbCollectionStatsResult,
    )
    def get_collection_stats(
        collection_id: str | None = Field(default=None, min_length=1, max_length=128),
    ) -> ToolResult[KbCollectionStatsResult]:
        """Get collection statistics."""
        stats = get_runtime().get_collection_stats(collection_id)
        return ok(KbCollectionStatsResult(
            collection_id=stats.collection_id,
            document_count=stats.document_count,
            total_size_bytes=stats.total_size_bytes,
        ))
