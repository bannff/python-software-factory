"""Strict enrollment and attempt binding tests for native handoffs."""
from __future__ import annotations

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolResult, ok, operational, service_only


class _EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_key: str
    manifest_digest: str


class _AttemptInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str


class _Output(BaseModel):
    changed: bool


def _fixture():
    effects: list[str] = []
    child = ToolCatalog("demo")

    @child.tool(name="demo_enroll")
    @service_only(callers={"agent"}, binding="enrollment")
    @operational(input_model=_EnrollmentInput, output_model=_Output)
    def enroll(run_key: str, manifest_digest: str) -> ToolResult[_Output]:
        effects.append(run_key)
        return ok(_Output(changed=True))

    @child.tool(name="demo_attempt")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_AttemptInput, output_model=_Output)
    def attempt(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str,
    ) -> ToolResult[_Output]:
        effects.append(attempt_id)
        return ok(_Output(changed=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child
    return aggregator, effects


def _call(
    aggregator, caller: str, tool: str, arguments: dict,
    *, enrollment=None, attempt=None,
):
    return NativeEnvelopeInvoker(aggregator).for_caller(caller)(
        {"brick_name": "demo", "tool_name": tool},
        arguments=arguments, idempotency_key="idem",
        envelope={"run_id": arguments.get("workflow_run_id", "")},
        enrollment=enrollment, attempt=attempt,
    )


def _enrollment() -> dict:
    return {"run_key": "enroll-1", "manifest_digest": "a" * 64}


def _attempt() -> dict:
    return {
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 3,
        "manifest_digest": "b" * 64,
    }


def test_each_operation_accepts_exactly_its_complete_binding() -> None:
    aggregator, effects = _fixture()
    enrolled = _call(
        aggregator, "agent", "enroll", _enrollment(), enrollment=_enrollment(),
    )
    attempted = _call(
        aggregator, "workflow", "attempt", _attempt(), attempt=_attempt(),
    )
    assert enrolled["ok"] is True
    assert attempted["ok"] is True
    assert effects == ["enroll-1", "attempt-1"]


@pytest.mark.parametrize("binding", [
    {},
    {"run_key": "enroll-1"},
    {"run_key": "enroll-1", "manifest_digest": "a" * 64, "attempt_id": "x"},
    {"workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 3,
     "manifest_digest": "b" * 64},
])
def test_enrollment_rejects_partial_extra_and_attempt_fields(binding) -> None:
    aggregator, effects = _fixture()
    result = _call(
        aggregator, "agent", "enroll", _enrollment(), enrollment=binding,
    )
    assert result["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


@pytest.mark.parametrize("binding", [
    {},
    {"workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 3},
    {"workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 3,
     "manifest_digest": "b" * 64, "run_key": "mixed"},
    {"run_key": "enroll-1", "manifest_digest": "a" * 64},
])
def test_attempt_rejects_partial_extra_and_enrollment_fields(binding) -> None:
    aggregator, effects = _fixture()
    result = _call(
        aggregator, "workflow", "attempt", _attempt(), attempt=binding,
    )
    assert result["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


def test_mixed_bindings_and_wrong_raw_fields_are_rejected() -> None:
    aggregator, effects = _fixture()
    mixed = _call(
        aggregator, "workflow", "attempt", _attempt(),
        enrollment=_enrollment(), attempt=_attempt(),
    )
    wrong = _call(
        aggregator, "workflow", "attempt",
        {**_attempt(), "attempt_id": "other"}, attempt=_attempt(),
    )
    assert mixed["error"]["type"] == "ServiceOnlyAccessError"
    assert wrong["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []
