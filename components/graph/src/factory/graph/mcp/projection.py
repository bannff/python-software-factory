"""Service-only Graph relationship projection MCP tool."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, get_envelope, operational, protected_canonical_json, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .projection_contracts import ProjectEventInput, ReconcileProjectionInput
from ..runtime.projection_reconcile import ReconcileResult, reconcile_projection
from ..runtime.relationship_projection import (
    ProjectionApplyResult, apply_projection,
)

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    @typed_tool(mcp)
    @service_only(callers={"events"}, binding="projection")
    @operational(input_model=ProjectEventInput, output_model=ProjectionApplyResult)
    def graph_project_event(
        tenant_id: str, owner_id: str, event_type: str,
        subject_id: str, revision: int, payload_digest: str,
        record: dict[str, Any], backend: str = "",
    ) -> ToolResult[ProjectionApplyResult]:
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != tenant_id \
                or ambient.get("principal_id") != owner_id:
            return ToolResult(ok=False, error="projection_authority_mismatch")
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        if selected not in runtime.available_backends():
            return ToolResult(ok=False, error="unknown_backend")
        try:
            return apply_projection(
                runtime.get_graph(selected), tenant_id=tenant_id,
                owner_id=owner_id, subject_id=subject_id,
                revision=revision, payload_digest=payload_digest, record=record,
            )
        except ValueError:
            return ToolResult(ok=False, error="invalid_projection")


    @typed_tool(mcp)
    @service_only(callers={"workflow"}, binding="projection")
    @operational(input_model=ReconcileProjectionInput, output_model=ReconcileResult)
    def graph_reconcile_projection(
        tenant_id: str, owner_id: str, event_type: str,
        subject_id: str, revision: int, payload_digest: str,
        source_system: str, snapshot_id: str, snapshot_digest: str,
        ordinal_start: int, records: list[dict[str, Any]],
        cursor: str | None = None, next_cursor: str | None = None,
        backend: str = "",
    ) -> ToolResult[ReconcileResult]:
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != tenant_id \
                or ambient.get("principal_id") != owner_id:
            return ToolResult(ok=False, error="projection_authority_mismatch")
        page = {
            "source_system": source_system, "snapshot_id": snapshot_id,
            "snapshot_digest": snapshot_digest, "ordinal_start": ordinal_start,
            "cursor": cursor, "next_cursor": next_cursor, "records": records,
        }
        expected = hashlib.sha256(protected_canonical_json(page)).hexdigest()
        if subject_id != snapshot_id or revision != ordinal_start \
                or payload_digest != expected:
            return ToolResult(ok=False, error="projection_payload_digest_mismatch")
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        if selected not in runtime.available_backends():
            return ToolResult(ok=False, error="unknown_backend")
        try:
            return reconcile_projection(
                runtime.get_graph(selected), tenant_id=tenant_id,
                owner_id=owner_id, source_system=source_system,
                snapshot_id=snapshot_id, snapshot_digest=snapshot_digest,
                ordinal_start=ordinal_start, cursor=cursor,
                next_cursor=next_cursor, page_digest=payload_digest,
                records=tuple(records),
            )
        except (TypeError, ValueError):
            return ToolResult(ok=False, error="invalid_projection_reconciliation")

__all__ = ["register"]
