"""Typed operational MCP tools for Events history."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, make_serializable, operational

from .contracts.operational import (
    HistoryListInput, HistoryOutput, HistoryQueryInput, PruneHistoryInput,
    PruneHistoryOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EventsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"]) -> None:
    """Register strict history tools."""

    @mcp.tool()
    @operational(input_model=HistoryListInput, output_model=HistoryOutput)
    def events_list_history(event_type: str | None = None, source: str | None = None,
                            tenant_id: str | None = None,
                            limit: int = 100) -> ToolResult[HistoryOutput]:
        entries = get_runtime().list_event_history(event_type=event_type, source=source,
                                                    tenant_id=tenant_id, limit=limit)
        rows = [_entry(entry, include_payload=False) for entry in entries]
        return {"entries": rows, "total": len(rows)}

    @mcp.tool()
    @operational(input_model=HistoryQueryInput, output_model=HistoryOutput)
    def events_query_history(event_type: str | None = None, source: str | None = None,
                             tenant_id: str | None = None, payload_key: str | None = None,
                             payload_value: str | None = None,
                             limit: int = 100) -> ToolResult[HistoryOutput]:
        entries = get_runtime().list_event_history(event_type=event_type, source=source,
            tenant_id=tenant_id, limit=limit)
        rows = [_entry(entry, include_payload=True) for entry in entries]
        if payload_key is not None:
            rows = [row for row in rows if str((row.get("payload") or {}).get(payload_key)) == str(payload_value)]
        return {"entries": rows, "total": len(rows)}

    @mcp.tool()
    @operational(input_model=PruneHistoryInput, output_model=PruneHistoryOutput)
    def events_prune_history(older_than_iso: str | None = None) -> ToolResult[PruneHistoryOutput]:
        runtime = get_runtime()
        before_count = runtime.count_event_history()
        deleted = runtime.prune_event_history(datetime.fromisoformat(older_than_iso) if older_than_iso else None)
        return {"ok": True, "deleted": deleted, "before_count": before_count,
                "after_count": runtime.count_event_history(),
                "retention_days": runtime.get_history_retention_days(),
                "older_than_iso": older_than_iso}


def _entry(entry: object, *, include_payload: bool) -> dict[str, object]:
    row = {"event_id": entry.event_id, "event_type": entry.event_type,
           "source": entry.source, "timestamp": entry.timestamp.isoformat(),
           "tenant_id": entry.tenant_id, "principal_id": entry.principal_id,
           "correlation_id": entry.correlation_id}
    if include_payload:
        row.update(payload=entry.payload, metadata=entry.metadata)
    return make_serializable(row)
