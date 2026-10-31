"""Typed blob and mutable-document Storage MCP tools."""
from __future__ import annotations

import base64
from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, operational

from .contracts.operational import BlobDeleteInput, BlobDeleteOutput, BlobGetInput, BlobGetOutput, BlobListInput, BlobListOutput, BlobPutInput, BlobPutOutput, BlobSummary, DocDeleteInput, DocDeleteOutput, DocFindInput, DocFindOutput, DocGetInput, DocGetOutput, DocInsertInput, DocInsertOutput, DocumentData

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register operational tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=BlobPutInput, output_model=BlobPutOutput)
    def blob_put(key: str, data: str, content_type: str = "text/plain") -> ToolResult[BlobPutOutput]:
        """Store a blob. Data should be base64 encoded for binary content."""
        try: content = base64.b64decode(data) if "base64" in content_type else data.encode()
        except Exception: content = data.encode()
        meta = get_runtime().get_blob_store().put(key, content, content_type)
        return BlobPutOutput(key=meta.key, size=meta.size, etag=meta.etag)

    @mcp.tool()
    @operational(input_model=BlobGetInput, output_model=BlobGetOutput)
    def blob_get(key: str) -> ToolResult[BlobGetOutput]:
        """Retrieve a blob by key."""
        content, meta = get_runtime().get_blob_store().get(key)
        data = base64.b64encode(content).decode() if meta.content_type.startswith("application/") else content.decode()
        return BlobGetOutput(key=meta.key, size=meta.size, content_type=meta.content_type, data=data)

    @mcp.tool()
    @operational(input_model=BlobDeleteInput, output_model=BlobDeleteOutput)
    def blob_delete(key: str) -> ToolResult[BlobDeleteOutput]:
        """Delete a blob by key."""
        return BlobDeleteOutput(deleted=get_runtime().get_blob_store().delete(key), key=key)

    @mcp.tool()
    @operational(input_model=BlobListInput, output_model=BlobListOutput)
    def blob_list(prefix: str = "", limit: int = 100) -> ToolResult[BlobListOutput]:
        """List blobs with optional prefix filter."""
        blobs = get_runtime().get_blob_store().list_keys(prefix, limit)
        return BlobListOutput(blobs=[BlobSummary(key=item.key, size=item.size) for item in blobs])

    @mcp.tool()
    @operational(input_model=DocInsertInput, output_model=DocInsertOutput)
    def doc_insert(collection: str, data: dict[str, object], doc_id: str | None = None) -> ToolResult[DocInsertOutput]:
        """Insert a document into a collection."""
        doc = get_runtime().get_document_store().insert(collection, data, doc_id)
        return DocInsertOutput(id=doc.id, collection=doc.collection)

    @mcp.tool()
    @operational(input_model=DocGetInput, output_model=DocGetOutput)
    def doc_get(collection: str, doc_id: str) -> ToolResult[DocGetOutput]:
        """Get a document by ID."""
        doc = get_runtime().get_document_store().get(collection, doc_id)
        if doc is None: return DocGetOutput(found=False, collection=collection, id=doc_id)
        return DocGetOutput(found=True, id=doc.id, collection=doc.collection, data=doc.data)

    @mcp.tool()
    @operational(input_model=DocFindInput, output_model=DocFindOutput)
    def doc_find(collection: str, query: dict[str, object], limit: int = 100) -> ToolResult[DocFindOutput]:
        """Find documents matching a query."""
        docs = get_runtime().get_document_store().find(collection, query, limit)
        return DocFindOutput(documents=[DocumentData(id=item.id, data=item.data) for item in docs])

    @mcp.tool()
    @operational(input_model=DocDeleteInput, output_model=DocDeleteOutput)
    def doc_delete(collection: str, doc_id: str) -> ToolResult[DocDeleteOutput]:
        """Delete a document."""
        return DocDeleteOutput(deleted=get_runtime().get_document_store().delete(collection, doc_id), collection=collection, id=doc_id)
