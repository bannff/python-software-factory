"""Test-only service-only fake provider for native gateway parity."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import ToolResult, ok, operational, service_only


class _ExecutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request: dict[str, Any]
    provider_request_digest: str
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str


class _ExecutionOutput(BaseModel):
    status: str
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str
    provider_request_digest: str


class _CancellationInput(BaseModel):
    """The generic cancellation owner tuple; providers receive no request body."""
    model_config = ConfigDict(extra="forbid", strict=True)
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str
    provider_request_digest: str


class _CancellationOutput(BaseModel):
    outcome: str
    attempt_id: str
    revision: int


def create_fake_provider(observed: list[dict[str, Any]]) -> ToolCatalog:
    """Return a provider that records only gateway-authorized exact bindings."""
    server = ToolCatalog("managed-lineage-fake-provider")

    @server.tool(name="execute_fake_compute_attempt")
    @service_only(callers={"workflow"}, binding="execution")
    @operational(input_model=_ExecutionInput, output_model=_ExecutionOutput)
    def execute(
        request: dict[str, Any], provider_request_digest: str, workflow_run_id: str,
        attempt_id: str, revision: int, engine_id: str, registration_digest: str,
        request_digest: str,
    ) -> ToolResult[_ExecutionOutput]:
        arguments = locals()
        observed.append(dict(arguments))
        return ok(_ExecutionOutput(status="completed", **arguments))

    @server.tool(name="cancel_fake_compute_attempt")
    @service_only(callers={"workflow"}, binding="execution")
    @operational(input_model=_CancellationInput, output_model=_CancellationOutput)
    def cancel(
        workflow_run_id: str, attempt_id: str, revision: int, engine_id: str,
        registration_digest: str, request_digest: str, provider_request_digest: str,
    ) -> ToolResult[_CancellationOutput]:
        arguments = locals()
        observed.append({"cancel": True, **arguments})
        return ok(_CancellationOutput(
            outcome="cancel_requested", attempt_id=attempt_id, revision=revision,
        ))

    return server
