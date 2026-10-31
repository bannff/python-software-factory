"""Typed immutable document-write MCP primitive."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.immutable import DocCreateOrMatchInput, DocCreateOrMatchOutput
from .contracts.base import JsonObject

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register the atomic document create-or-match operation."""

    @mcp.tool()
    @operational(input_model=DocCreateOrMatchInput, output_model=DocCreateOrMatchOutput)
    def doc_create_or_match(collection: str, doc_id: str, data: JsonObject, content_hash: str) -> ToolResult[DocCreateOrMatchOutput]:
        """Create immutable data, match an equal retry, or return a conflict."""
        writer = getattr(get_runtime().get_document_store(), "create_or_match", None)
        if writer is None:
            return DocCreateOrMatchOutput(status="unsupported", id=doc_id, collection=collection, content_hash=content_hash)
        result = writer(collection, doc_id, data, content_hash)
        return DocCreateOrMatchOutput(status=result.status, id=doc_id, collection=collection, content_hash=content_hash, existing_content_hash=result.existing_content_hash or "")
