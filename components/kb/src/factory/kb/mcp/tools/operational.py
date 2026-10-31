"""Operational MCP tools for KB brick — typed ingress/egress."""
from __future__ import annotations
from typing import Any, Callable
from pydantic import Field
from factory.mcp_utils.interface import ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult
from ...models.ingest import KbGraphReference, KbIngestRequest, KbIngestResult
from ...models.ops import (
    KbBackfillRequest,
    KbBackfillResult,
    KbDeleteDocumentResult,
    KbDocumentIdRequest,
    KbGetDocumentResult,
    KbListDocumentsRequest,
    KbListDocumentsResult,
    KbSearchHit,
    KbSearchRequest,
    KbSearchResult,
)
from ...runtime.envelope import ContextEnvelope
from .projection import digest_content, digest_tombstone, emit_kb_projection


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    """Register operational KB tools."""

    @mcp.tool()
    @operational(input_model=KbIngestRequest, output_model=KbIngestResult)
    def ingest(
        content: str = Field(..., min_length=1),
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        document_id: str | None = Field(
            default=None, max_length=128, pattern=r"^[a-z0-9_\-]+$"
        ),
        extract_entities: bool | None = None,
        graph_references: list[dict[str, Any]] | None = None,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ToolResult[KbIngestResult]:
        """Ingest a document (typed ToolResult egress; idempotent when keyed)."""
        runtime = get_runtime()
        envelope = ContextEnvelope(tenant_id=tenant_id, principal_id=principal_id)
        result = runtime.ingest(
            content=content,
            metadata=metadata,
            source=source,
            document_id=document_id,
            envelope=envelope,
            extract_entities=extract_entities,
        )
        references = [
            KbGraphReference.model_validate(item).model_dump(mode="json")
            for item in (graph_references or [])
        ]
        if result.status == "ingested":
            emit_kb_projection(
                result.document_id, content_digest=digest_content(content),
                references=references, tenant_id=tenant_id,
                principal_id=principal_id,
            )
        extraction = None
        if result.extraction_status:
            extraction = {
                "status": result.extraction_status,
                "entities_created": result.entities_created,
                "relationships_created": result.relationships_created,
            }
            if result.extraction_message:
                extraction["message"] = result.extraction_message
        return ok(
            KbIngestResult(
                document_id=result.document_id,
                status=result.status,
                extraction=extraction,
            ),
            idempotency_key=idempotency_key,
        )

    @mcp.tool()
    @operational(input_model=KbSearchRequest, output_model=KbSearchResult)
    def search(
        query: str = Field(..., min_length=1),
        limit: int = Field(default=10, ge=1, le=1000),
        filters: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ToolResult[KbSearchResult]:
        """Search the knowledge base."""
        runtime = get_runtime()
        envelope = ContextEnvelope(tenant_id=tenant_id, principal_id=principal_id)
        results = runtime.search(
            query=query, limit=limit, filters=filters, envelope=envelope
        )
        hits = [
            KbSearchHit(
                document_id=r.document_id,
                content=r.content,
                score=round(r.score, 3),
                source=r.metadata.get("source", ""),
            )
            for r in results
        ]
        return ok(KbSearchResult(results=hits, total=len(hits)))

    @mcp.tool()
    @operational(input_model=KbDocumentIdRequest, output_model=KbGetDocumentResult)
    def get_document(
        document_id: str = Field(..., min_length=1),
        idempotency_key: str | None = None,
    ) -> ToolResult[KbGetDocumentResult]:
        """Get a document by ID."""
        runtime = get_runtime()
        document = runtime.get_document(document_id)
        if document is None:
            return ok(KbGetDocumentResult(found=False, error="Not found"))
        return ok(
            KbGetDocumentResult(
                found=True,
                document={"id": document.id, "content": document.content},
            )
        )

    @mcp.tool()
    @operational(input_model=KbDocumentIdRequest, output_model=KbDeleteDocumentResult)
    def delete_document(
        document_id: str = Field(..., min_length=1),
        idempotency_key: str | None = None,
    ) -> ToolResult[KbDeleteDocumentResult]:
        """Delete a document by ID."""
        runtime = get_runtime()
        deleted = runtime.delete_document(document_id)
        if deleted:
            emit_kb_projection(
                document_id, content_digest=digest_tombstone(document_id),
                references=[], tenant_id=None, principal_id=None,
                action="tombstone",
            )
        return ok(KbDeleteDocumentResult(ok=deleted, document_id=document_id))

    @mcp.tool()
    @operational(input_model=KbListDocumentsRequest, output_model=KbListDocumentsResult)
    def list_documents(
        limit: int = Field(default=100, ge=1, le=10_000),
        idempotency_key: str | None = None,
    ) -> ToolResult[KbListDocumentsResult]:
        """List documents."""
        runtime = get_runtime()
        documents = runtime.list_documents(limit=limit)
        rows = [{"id": d.id, "source": d.source} for d in documents]
        return ok(KbListDocumentsResult(documents=rows, total=len(rows)))

    @mcp.tool()
    @operational(input_model=KbBackfillRequest, output_model=KbBackfillResult)
    def backfill_embeddings(
        limit: int = Field(default=100, ge=1, le=10_000),
        idempotency_key: str | None = None,
    ) -> ToolResult[KbBackfillResult]:
        """Backfill embeddings for documents that lack them."""
        runtime = get_runtime()
        vs = getattr(runtime, "_vector_store", None)
        if vs is None or not hasattr(vs, "backfill_embeddings"):
            return ok(
                KbBackfillResult(error="Backfill requires Neo4j vector store backend")
            )
        count = vs.backfill_embeddings(limit=limit)
        return ok(KbBackfillResult(backfilled=count, limit=limit))

    @mcp.tool()
    @operational(input_model=KbSearchRequest, output_model=KbSearchResult)
    def search_remote(
        query: str = Field(..., min_length=1),
        limit: int = Field(default=10, ge=1, le=1000),
        filters: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ToolResult[KbSearchResult]:
        """Search the remote AWS knowledge base (Bedrock KB / GraphRAG)."""
        runtime = get_runtime()
        try:
            results = runtime.search_remote(
                query=query, limit=limit, filters=filters
            )
        except RuntimeError as e:
            return ok(KbSearchResult(error=str(e), results=[], total=0))
        hits = [
            KbSearchHit(
                document_id=r.document_id,
                content=r.content,
                score=round(r.score, 3),
                source=r.metadata.get("s3_uri", r.metadata.get("source", "")),
            )
            for r in results
        ]
        return ok(KbSearchResult(results=hits, total=len(hits), backend="bedrock"))
