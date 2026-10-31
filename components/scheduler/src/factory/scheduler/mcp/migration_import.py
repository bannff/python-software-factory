"""Service-only Migration import of one paused schedule.

Callable only by the in-process ``migration`` service through the exact
``migration_import`` binding. The handler re-asserts owner authority from the
ambient envelope, recomputes the canonical target digest before any effect,
and persists directly in the paused state via the existing lifecycle/SQL
adapter. It never imports ``factory.migration``.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, ok, operational, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .import_contracts import (
    ImportScheduleDefinition, SchedulerImportInput, SchedulerImportOutput,
)
from ..runtime.import_records import import_paused_schedule


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp, name="scheduler_import_record")
    @service_only(callers={"migration"}, binding="migration_import")
    @operational(
        input_model=SchedulerImportInput,
        output_model=SchedulerImportOutput,
        idempotent=False,
    )
    def scheduler_import_record(
        tenant_id: str, owner_id: str, source_adapter: str,
        source_fingerprint: str, plan_digest: str, kind: str,
        source_record_id: str, target_digest: str, schedule: dict[str, Any],
    ) -> ToolResult[SchedulerImportOutput]:
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != tenant_id \
                or ambient.get("principal_id") != owner_id:
            return fail("scheduler_import_authority_mismatch")
        if kind != "schedules":
            return fail("scheduler_import_kind_unsupported")
        origin_session_id = ambient.get("session_id")
        origin_thread_id = ambient.get("thread_id")
        if not isinstance(origin_session_id, str) or not isinstance(origin_thread_id, str):
            return fail("scheduler_import_origin_required")
        definition = ImportScheduleDefinition.model_validate(schedule).model_dump(
            mode="json",
        )
        try:
            result = import_paused_schedule(
                get_runtime().lifecycle, tenant_id=tenant_id, owner_id=owner_id,
                source_adapter=source_adapter, source_record_id=source_record_id,
                expected_digest=target_digest, definition=definition,
                origin_session_id=origin_session_id,
                origin_thread_id=origin_thread_id,
            )
        except ValueError as exc:
            message = str(exc)
            return fail(message if message.startswith("scheduler_import_")
                        else "scheduler_import_invalid")
        return ok(SchedulerImportOutput(
            imported=result.imported, replayed=result.replayed,
            schedule=result.schedule,
        ))


__all__ = ["register"]
