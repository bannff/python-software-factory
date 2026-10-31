"""Real MCP 2.1.1 canaries for elicitation-only MRTR preparation."""

from __future__ import annotations

from typing import Any

import pytest
from mcp import Client
from mcp.client._input_required import InputRequiredRoundsExceededError
from mcp.shared.exceptions import MCPError
from mcp.types import ElicitResult, InputRequiredResult, ListRootsResult
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.runtime.elicitation import (
    ElicitationFormRequest,
    ElicitationResponse,
)
from factory.mcp_utils.runtime.native_v2_capability_client import NativeV2ScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityInvocation

from .mrtr_harness import ApprovalDTO, mrtr_choice_surface, mrtr_surface


class NestedDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    nested: ApprovalDTO


def test_elicitation_form_rejects_nested_response_models() -> None:
    with pytest.raises(ValueError, match="flat primitive"):
        ElicitationFormRequest("Invalid nested form", NestedDTO)


@pytest.mark.asyncio
async def test_first_round_is_form_input_required_without_terminal_effect() -> None:
    calls: list[int] = []
    server, _ = mrtr_surface(calls)

    async with Client(server) as client:
        result = await client.session.call_tool(
            "effect", {"value": 7}, allow_input_required=True,
        )

    assert isinstance(result, InputRequiredResult)
    assert result.request_state is None
    assert list(result.input_requests or {}) == ["elicitation"]
    request = result.input_requests["elicitation"]
    assert request.method == "elicitation/create" and request.params.mode == "form"
    assert calls == []


@pytest.mark.asyncio
async def test_accept_auto_retries_and_executes_terminal_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    server, scope = mrtr_surface(calls)

    async def accept(_: Any) -> ElicitationResponse:
        return ElicitationResponse("accept", {"approved": True})

    client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=accept)
    result = await client.invoke(CapabilityInvocation("effect", {"value": 7}, "key"))

    assert result.is_error is False
    assert result.structured_content["data"] == {"value": 7}
    assert calls == [7]
    assert [event["phase"] for event in events] == ["start", "result"]
    assert all(event["args_summary"] == {} for event in events)
    assert "approved" not in repr(events)
    await client.close()


@pytest.mark.asyncio
async def test_first_round_offers_string_enum_choice_without_terminal_effect() -> None:
    answers: list[str] = []
    server, _ = mrtr_choice_surface(answers)

    async with Client(server) as client:
        result = await client.session.call_tool(
            "effect", {"value": 3}, allow_input_required=True,
        )

    assert isinstance(result, InputRequiredResult)
    request = result.input_requests["elicitation"]
    schema = request.params.requested_schema
    assert schema["properties"]["answer"]["enum"] == ["yes", "no", "maybe"]
    assert answers == []


@pytest.mark.asyncio
async def test_accept_with_chosen_enum_value_executes_terminal_exactly_once() -> None:
    answers: list[str] = []
    server, scope = mrtr_choice_surface(answers)

    async def choose(_: Any) -> ElicitationResponse:
        return ElicitationResponse("accept", {"answer": "maybe"})

    client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=choose)
    result = await client.invoke(CapabilityInvocation("effect", {"value": 3}, "key"))

    assert result.is_error is False
    assert result.structured_content["data"] == {"value": 3}
    assert answers == ["maybe"]
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_refusal_is_terminal_error_without_effect(action: str) -> None:
    calls: list[int] = []
    server, scope = mrtr_surface(calls)

    async def refuse(_: Any) -> ElicitationResponse:
        return ElicitationResponse(action)  # type: ignore[arg-type]

    client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=refuse)
    result = await client.invoke(CapabilityInvocation("effect", {"value": 1}, "key"))
    assert result.is_error is True and calls == []
    await client.close()


@pytest.mark.asyncio
async def test_malformed_or_missing_elicitation_never_executes() -> None:
    calls: list[int] = []
    server, scope = mrtr_surface(calls)

    async def malformed(_: Any) -> ElicitationResponse:
        return ElicitationResponse("accept", {"approved": True, "extra": "no"})

    malformed_client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=malformed)
    assert (await malformed_client.invoke(
        CapabilityInvocation("effect", {"value": 1}, "key")
    )).is_error is True
    await malformed_client.close()

    missing_client = NativeV2ScopedCapabilityClient(server, scope)
    with pytest.raises(MCPError, match="Elicitation not supported"):
        await missing_client.invoke(CapabilityInvocation("effect", {"value": 2}, "key"))
    assert calls == []
    await missing_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses",
    [
        {"unexpected": ElicitResult(action="accept", content={"approved": True})},
        {"elicitation": ListRootsResult(roots=[])},
    ],
)
async def test_unexpected_response_key_or_type_never_executes(responses: Any) -> None:
    calls: list[int] = []
    server, _ = mrtr_surface(calls)
    async with Client(server) as client:
        result = await client.session.call_tool(
            "effect", {"value": 1}, input_responses=responses,
            allow_input_required=True,
        )
    assert result.is_error is True and calls == []


@pytest.mark.asyncio
async def test_max_round_and_callback_errors_propagate_without_effect() -> None:
    calls: list[int] = []
    server, scope = mrtr_surface(calls, stubborn=True)

    async def accept(_: Any) -> ElicitationResponse:
        return ElicitationResponse("accept", {"approved": True})

    client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=accept)
    with pytest.raises(InputRequiredRoundsExceededError):
        await client.invoke(CapabilityInvocation("effect", {"value": 1}, "key"))
    await client.close()

    async def broken(_: Any) -> ElicitationResponse:
        raise RuntimeError("callback failed")

    server, scope = mrtr_surface(calls)
    client = NativeV2ScopedCapabilityClient(server, scope, elicitation_handler=broken)
    with pytest.raises(BaseExceptionGroup) as exc_info:
        await client.invoke(CapabilityInvocation("effect", {"value": 2}, "key"))
    assert exc_info.value.subgroup(RuntimeError) is not None
    assert calls == []
    await client.close()
