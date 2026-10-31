"""Workflow-owned bounded source paging for Graph projection recovery."""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import get_service, protected_canonical_json


class ProjectionSourcePage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    snapshot_id: str = Field(min_length=1, max_length=128)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=256)
    next_cursor: str | None = Field(default=None, max_length=256)


class ProjectionPageReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ordinal_start: int = Field(ge=0)
    scanned: int = Field(ge=1)
    next_cursor: str | None = None


def reconcile_source_pages(
    *, tenant_id: str, owner_id: str, source_system: str,
    load_page: Callable[[str | None, int], Mapping[str, Any]],
    page_size: int = 100, max_pages: int = 100,
) -> tuple[ProjectionPageReceipt, ...]:
    """Load immutable source pages and replay them through Graph's protected seam."""
    if not tenant_id or not owner_id or not source_system:
        raise ValueError("projection reconciliation authority is incomplete")
    if not 1 <= page_size <= 256 or not 1 <= max_pages <= 100:
        raise ValueError("projection reconciliation bounds are invalid")
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("workflow Graph reconciliation unavailable")
    cursor = None
    seen_cursors: set[str | None] = {None}
    ordinal = 0
    snapshot: tuple[str, str] | None = None
    receipts = []
    for _ in range(max_pages):
        page = ProjectionSourcePage.model_validate(load_page(cursor, page_size))
        if any(
            item.get("record", {}).get("source_system") != source_system
            for item in page.records
        ):
            raise RuntimeError("projection page contains a foreign source record")
        current = (page.snapshot_id, page.snapshot_digest)
        if snapshot is not None and current != snapshot:
            raise RuntimeError("projection source snapshot changed during paging")
        snapshot = current
        payload = {
            "source_system": source_system, "snapshot_id": page.snapshot_id,
            "snapshot_digest": page.snapshot_digest, "ordinal_start": ordinal,
            "cursor": cursor, "next_cursor": page.next_cursor,
            "records": list(page.records),
        }
        digest = hashlib.sha256(protected_canonical_json(payload)).hexdigest()
        binding = {
            "tenant_id": tenant_id, "owner_id": owner_id,
            "event_type": "graph.projection.reconcile",
            "subject_id": page.snapshot_id, "revision": ordinal,
            "payload_digest": digest,
        }
        raw = invoke(
            {"brick_name": "graph", "tool_name": "graph_reconcile_projection"},
            arguments={**binding, **payload},
            idempotency_key=f"projection-reconcile:{source_system}:{page.snapshot_id}:{ordinal}",
            envelope={"tenant_id": tenant_id, "principal_id": owner_id},
            projection=binding,
        )
        structured = raw.get("result", {}).get("structured_content") \
            if isinstance(raw, dict) else None
        data = structured.get("data") \
            if isinstance(structured, dict) and structured.get("ok") is True else None
        if not isinstance(data, dict):
            raise RuntimeError("workflow Graph reconciliation failed")
        receipts.append(ProjectionPageReceipt(
            ordinal_start=ordinal, scanned=len(page.records),
            next_cursor=page.next_cursor,
        ))
        ordinal += len(page.records)
        if page.next_cursor is None:
            return tuple(receipts)
        if page.next_cursor in seen_cursors:
            raise RuntimeError("projection source cursor did not advance")
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor
    raise RuntimeError("projection source page limit exceeded")


__all__ = ["ProjectionPageReceipt", "ProjectionSourcePage", "reconcile_source_pages"]
