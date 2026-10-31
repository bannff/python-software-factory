"""Public Migration lifecycle tools over Workflow-owned execution."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, get_service, ok, operational,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.lifecycle import project_progress, start_plan
from ..runtime.preview import PreviewRuntime
from .execution_contracts import ApplyPageRequest
from .lifecycle_contracts import (
    MigrationGetInput, MigrationGetOutput, MigrationStartInput, MigrationStartOutput,
)
from .operational import _authority

_ERROR = "migration_lifecycle_unavailable"


def _invoker():
    factory = get_service("tool_invoker_for_caller")
    if not callable(factory):
        raise ValueError(_ERROR)
    invoke = factory("migration")
    if not callable(invoke):
        raise ValueError(_ERROR)
    return invoke


def register(mcp: Any, get_runtime: Callable[[], PreviewRuntime]) -> None:
    @typed_tool(mcp)
    @operational(input_model=MigrationStartInput, output_model=MigrationStartOutput)
    def migration_start(
        plan_digest: str, kinds: list[str], source: str = "kirocrew-v1",
    ) -> ToolResult[MigrationStartOutput]:
        try:
            tenant, owner = _authority()
            runtime = get_runtime()
            plan = runtime.receipts.find_plan(
                tenant, owner, source, plan_digest)
            if plan is None or tuple(kinds) != plan.kinds:
                return fail(_ERROR)
            return ok(start_plan(plan, _invoker(), dict(get_envelope() or {})))
        except Exception:  # noqa: BLE001 — fixed safe lifecycle boundary
            return fail(_ERROR)

    @typed_tool(mcp)
    @deterministic(input_model=MigrationGetInput, output_model=MigrationGetOutput)
    def migration_get(run_id: str) -> ToolResult[MigrationGetOutput]:
        try:
            _authority()
            return ok(project_progress(
                get_runtime().receipts, _invoker(),
                dict(get_envelope() or {}), run_id))
        except Exception:  # noqa: BLE001 — fixed safe lifecycle boundary
            return fail(_ERROR)


__all__ = ["register"]
