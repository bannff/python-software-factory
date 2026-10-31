"""Orthogonal service-only metadata and protected state contracts."""
from __future__ import annotations

import contextvars

import pytest
from pydantic import BaseModel, ConfigDict, field_validator

from factory.mcp_utils.interface import (
    AttemptBinding, EnrollmentBinding, InternalInvocationClaims,
    ServiceOnlyAccessError, ToolResult, ok, operational, service_binding,
    service_callers, service_only,
)


def test_service_only_is_orthogonal_in_either_decorator_order() -> None:
    @service_only(callers={"workflow"}, binding="attempt")
    @operational
    def outer() -> None:
        return None

    @operational
    @service_only(callers={"workflow"}, binding="enrollment")
    def inner() -> None:
        return None

    assert outer._mcp_category == inner._mcp_category == "operational"
    assert service_callers(outer) == service_callers(inner) == frozenset({"workflow"})
    assert service_binding(outer) == "attempt"
    assert service_binding(inner) == "enrollment"


@pytest.mark.parametrize("binding", ["", "other", None])
def test_service_only_rejects_unknown_binding_kind(binding) -> None:
    with pytest.raises(ValueError, match="binding"):
        service_only(callers={"workflow"}, binding=binding)


def test_operation_bindings_are_strict() -> None:
    enrollment = EnrollmentBinding(run_key="run-key", manifest_digest="a" * 64)
    attempt = AttemptBinding(
        workflow_run_id="run-1", attempt_id="attempt-1", revision=2,
        manifest_digest="b" * 64,
    )
    assert enrollment.run_key == "run-key"
    assert attempt.revision == 2
    with pytest.raises(ValueError, match="SHA-256"):
        EnrollmentBinding(run_key="run-key", manifest_digest="forged")
    with pytest.raises(ValueError, match="revision"):
        AttemptBinding(
            workflow_run_id="run-1", attempt_id="attempt-1", revision=True,
            manifest_digest="b" * 64,
        )
    with pytest.raises(TypeError, match="must be minted"):
        InternalInvocationClaims(
            "workflow", "agent", "agent_enroll", enrollment, object(),
            authority=object(),
        )


def test_unauthorized_call_precedes_pydantic_validator_and_handler() -> None:
    validation_effects: list[str] = []
    handler_effects: list[str] = []

    class Input(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        workflow_run_id: str
        attempt_id: str
        revision: int
        manifest_digest: str

        @field_validator("workflow_run_id")
        @classmethod
        def observe(cls, value: str) -> str:
            validation_effects.append(value)
            return value

    class Output(BaseModel):
        changed: bool

    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=Input, output_model=Output)
    def protected(**kwargs) -> ToolResult[Output]:
        handler_effects.append(kwargs["workflow_run_id"])
        return ok(Output(changed=True))

    arguments = {
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 2,
        "manifest_digest": "a" * 64,
    }
    with pytest.raises(ServiceOnlyAccessError, match="native dispatch"):
        protected(**arguments)
    with pytest.raises(ServiceOnlyAccessError, match="native dispatch"):
        contextvars.copy_context().run(protected, **arguments)
    assert validation_effects == []
    assert handler_effects == []
