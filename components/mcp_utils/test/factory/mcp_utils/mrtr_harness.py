"""Shared real-MCP harness for elicitation-only MRTR tests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.runtime.elicitation import (
    ElicitationFormRequest,
    ElicitationResponse,
    PrepareNeedsElicitation,
    PrepareReady,
)
from factory.mcp_utils.runtime.native_v2_composer import (
    NativeMCPV2Composer,
    NativeToolRegistration,
)
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)
from factory.mcp_utils.runtime.tool_result import ToolResult, ok
from factory.mcp_utils.runtime.typed_boundary import apply_category


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int
    approved: bool | None = None


class ApprovalDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: bool


class OutputDTO(BaseModel):
    value: int


def mrtr_surface(
    calls: list[int], *, stubborn: bool = False,
) -> tuple[Any, CapabilityScope]:
    """Build one interactive tool whose terminal call is observable."""
    def terminal(value: int, approved: bool | None = None) -> ToolResult[OutputDTO]:
        assert approved is True
        calls.append(value)
        return ok(OutputDTO(value=value))

    def prepare(arguments: Any, response: ElicitationResponse | None) -> Any:
        request = ElicitationFormRequest("Approve execution", ApprovalDTO)
        if response is None or stubborn:
            return PrepareNeedsElicitation(request)
        assert response.content is not None
        return PrepareReady({**arguments, "approved": response.content["approved"]})

    handler = apply_category(
        terminal, "operational", input_model=InputDTO, output_model=OutputDTO,
    )
    identity = ServerSurfaceIdentity(
        entry_point="elicitation-canary", route_bindings=("/mcp",),
        transport_bindings=("in_process", "http"), process_lifecycle_id="test",
        catalog_digest="catalog", scope_digest="scope", policy_digest="policy",
        closure_digest="closure",
    )
    plan = ServerCompositionPlan(identity, "flat", frozenset({"effect"}))
    registration = NativeToolRegistration("effect", "Effect", handler, prepare=prepare)
    server = NativeMCPV2Composer(plan, (registration,)).compose()
    return server, CapabilityScope.create("policy", {"effect"})


class ChoiceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: Literal["yes", "no", "maybe"]


class ChoiceInputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int
    answer: str | None = None


def mrtr_choice_surface(answers: list[str]) -> tuple[Any, CapabilityScope]:
    """Build one interactive tool whose terminal call records a string-enum answer."""
    def terminal(value: int, answer: str | None = None) -> ToolResult[OutputDTO]:
        assert answer is not None
        answers.append(answer)
        return ok(OutputDTO(value=value))

    def prepare(arguments: Any, response: ElicitationResponse | None) -> Any:
        request = ElicitationFormRequest("Choose one", ChoiceDTO)
        if response is None:
            return PrepareNeedsElicitation(request)
        assert response.content is not None
        return PrepareReady({**arguments, "answer": response.content["answer"]})

    handler = apply_category(
        terminal, "operational", input_model=ChoiceInputDTO, output_model=OutputDTO,
    )
    identity = ServerSurfaceIdentity(
        entry_point="elicitation-choice-canary", route_bindings=("/mcp",),
        transport_bindings=("in_process", "http"), process_lifecycle_id="test",
        catalog_digest="catalog", scope_digest="scope", policy_digest="policy",
        closure_digest="closure",
    )
    plan = ServerCompositionPlan(identity, "flat", frozenset({"effect"}))
    registration = NativeToolRegistration("effect", "Effect", handler, prepare=prepare)
    server = NativeMCPV2Composer(plan, (registration,)).compose()
    return server, CapabilityScope.create("policy", {"effect"})


__all__ = ["ApprovalDTO", "ChoiceDTO", "mrtr_choice_surface", "mrtr_surface"]
