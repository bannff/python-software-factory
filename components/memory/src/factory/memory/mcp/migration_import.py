"""Protected service-only Memory import MCP tool (M7 slice 2).

``memory_import_record`` is callable only by the in-process ``migration``
service under a ``migration_import`` binding. It recomputes the declared
``target_digest`` over the documented canonical target material and rejects any
mismatch before writing, then performs a target-native, source-record
idempotent store through Memory's own primitives.
"""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import (
    ToolResult, get_envelope, get_service, operational, service_only,
)

from factory.memory.runtime.idempotency import MemoryIdempotencyError
from factory.memory.runtime.migration_import import (
    ERR_UNAVAILABLE, MigrationImportError, import_memory_record,
)
from factory.memory.runtime.runtime import MemoryRuntime

from .contracts.migration_import import MemoryImportInput, MemoryImportOutput

_CONFLICT = "memory import conflict"


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register the protected ``memory_import_record`` tool."""

    @mcp.tool(name="memory_import_record")
    @service_only(callers={"migration"}, binding="migration_import")
    @operational(
        input_model=MemoryImportInput, output_model=MemoryImportOutput,
        idempotent=False,
    )
    def memory_import_record(
        tenant_id: str, owner_id: str, source_adapter: str,
        source_fingerprint: str, plan_digest: str, kind: str,
        source_record_id: str, target_digest: str, subtype: str,
        content: str, key: str, tags: tuple[str, ...] = (),
    ) -> ToolResult[MemoryImportOutput]:
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != tenant_id \
                or ambient.get("principal_id") != owner_id:
            return {"imported": False, "error": "memory import authority mismatch"}
        invoker = get_service("tool_invoker")
        if not callable(invoker):
            return {"imported": False, "error": ERR_UNAVAILABLE}
        try:
            outcome, memory_id = import_memory_record(
                runtime, invoker, tenant_id=tenant_id, owner_id=owner_id,
                source_adapter=source_adapter,
                source_fingerprint=source_fingerprint, plan_digest=plan_digest,
                kind=kind, source_record_id=source_record_id,
                target_digest=target_digest, subtype=subtype, content=content,
                key=key, tags=tags,
            )
        except MigrationImportError as exc:
            return {"imported": False, "error": exc.safe}
        except MemoryIdempotencyError:
            return {"imported": False, "error": _CONFLICT}
        return {"imported": True, "outcome": outcome, "memory_id": memory_id}


__all__ = ["register"]
