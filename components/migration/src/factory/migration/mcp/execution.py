"""Service-only Workflow execution target for Migration plan pages."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, fail, get_envelope, get_service, ok, operational, service_only,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.apply_execution import apply_plan_page
from ..runtime.preview import PreviewRuntime
from .execution_contracts import ApplyExecutionInput, ApplyExecutionOutput, ApplyPageRequest

_ERROR = "migration_apply_unavailable"


def register(mcp: Any, get_runtime: Callable[[], PreviewRuntime]) -> None:
    @typed_tool(mcp)
    @service_only(callers={"workflow"}, binding="execution")
    @operational(
        input_model=ApplyExecutionInput, output_model=ApplyExecutionOutput,
        idempotent=False,
    )
    def migration_apply_execution(
        request: dict[str, Any], provider_request_digest: str,
        workflow_run_id: str, attempt_id: str, revision: int,
        engine_id: str, registration_digest: str, request_digest: str,
    ) -> ToolResult[ApplyExecutionOutput]:
        del provider_request_digest, workflow_run_id, attempt_id, revision
        del engine_id, registration_digest, request_digest
        ambient = get_envelope()
        if not isinstance(ambient, dict):
            return fail(_ERROR)
        try:
            parsed = ApplyPageRequest.model_validate(request)
        except ValueError:
            return fail(_ERROR)
        if ambient.get("tenant_id") != parsed.tenant_id \
                or ambient.get("principal_id") != parsed.owner_id:
            return fail(_ERROR)
        factory = get_service("tool_invoker_for_caller")
        if not callable(factory):
            return fail(_ERROR)
        invoker = factory("migration")
        if not callable(invoker):
            return fail(_ERROR)
        try:
            result = apply_plan_page(
                get_runtime().receipts, invoker, dict(ambient), parsed)
        except Exception:  # noqa: BLE001 — fixed safe execution failure
            return fail(_ERROR)
        return ok(result)


__all__ = ["register"]
