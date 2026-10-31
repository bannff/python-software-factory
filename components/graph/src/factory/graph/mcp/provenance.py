"""Typed MCP tools for durable Graph provenance projection."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.provenance_models import (
    DurableSourcePage,
    GraphRebuildRequest,
    GraphRebuildResult,
    GraphRelationshipWrite,
    GraphTombstone,
    GraphWriteResult,
)
from ..runtime.provenance_ports import GraphProvenanceUnsupportedError
from .provenance_models import GraphRebuildInput, GraphTombstoneInput, GraphWriteInput

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def _graph(runtime: "GraphRuntime", backend: str):
    return runtime.get_graph(backend or runtime.default_backend)


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register deterministic provenance mutations on the existing Graph port."""

    @typed_tool(mcp)
    @operational(input_model=GraphWriteInput, output_model=GraphWriteResult)
    def graph_write_relationship(
        source_system: str, source_identity: str, source_digest: str,
        relation_type: str, source_endpoint: str, target_endpoint: str,
        source_ref: str, visibility: str, browse_metadata: dict | None = None,
        backend: str = "",
    ) -> ToolResult[GraphWriteResult]:
        parsed = GraphWriteInput(
            source_system=source_system, source_identity=source_identity,
            source_digest=source_digest, relation_type=relation_type,
            source_endpoint=source_endpoint, target_endpoint=target_endpoint,
            source_ref=source_ref, visibility=visibility,
            browse_metadata=browse_metadata or {}, backend=backend,
        )
        write = GraphRelationshipWrite.model_validate(
            parsed.model_dump(exclude={"backend"}),
        )
        try:
            return _graph(get_runtime(), backend).write_relationship(write)
        except GraphProvenanceUnsupportedError as exc:
            return ToolResult(ok=False, error=exc.code)

    @typed_tool(mcp)
    @operational(input_model=GraphTombstoneInput, output_model=GraphWriteResult)
    def graph_tombstone_relationship(
        source_system: str, source_identity: str, source_digest: str,
        deleted_at: datetime, backend: str = "",
    ) -> ToolResult[GraphWriteResult]:
        parsed = GraphTombstoneInput(
            source_system=source_system, source_identity=source_identity,
            source_digest=source_digest, deleted_at=deleted_at, backend=backend,
        )
        tombstone = GraphTombstone.model_validate(
            parsed.model_dump(exclude={"backend"}),
        )
        try:
            return _graph(get_runtime(), backend).tombstone_relationship(tombstone)
        except GraphProvenanceUnsupportedError as exc:
            return ToolResult(ok=False, error=exc.code)

    @typed_tool(mcp)
    @operational(input_model=GraphRebuildInput, output_model=GraphRebuildResult)
    def graph_rebuild(
        source_system: str, snapshot_id: str, snapshot_digest: str,
        ordinal_start: int, records: list[dict], next_cursor: str | None = None,
        cursor: str | None = None, checkpoint: dict | None = None,
        backend: str = "",
    ) -> ToolResult[GraphRebuildResult]:
        parsed = GraphRebuildInput(
            source_system=source_system, snapshot_id=snapshot_id,
            snapshot_digest=snapshot_digest, ordinal_start=ordinal_start,
            records=records, next_cursor=next_cursor, cursor=cursor,
            checkpoint=checkpoint, backend=backend,
        )
        request = GraphRebuildRequest(
            source_system=parsed.source_system, snapshot_id=parsed.snapshot_id,
            snapshot_digest=parsed.snapshot_digest, cursor=parsed.cursor,
            checkpoint=parsed.checkpoint,
        )
        page = DurableSourcePage(
            snapshot_id=parsed.snapshot_id, snapshot_digest=parsed.snapshot_digest,
            ordinal_start=parsed.ordinal_start, records=tuple(parsed.records),
            next_cursor=parsed.next_cursor,
        )
        try:
            return _graph(get_runtime(), backend).rebuild(request, page)
        except GraphProvenanceUnsupportedError as exc:
            return ToolResult(ok=False, error=exc.code)
