"""Two-domain native MCP-v2 observability and protected-redaction tests."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.context import reset_envelope, set_envelope
from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registry import get_service, set_service
from factory.mcp_utils.runtime.native_v2_composer import (
    NativeMCPV2Composer,
    NativeToolRegistration,
)
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.tool_result import ToolResult, ok


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int


class OutputDTO(BaseModel):
    domain: str
    value: int


def _plan(names: frozenset[str]) -> ServerCompositionPlan:
    identity = ServerSurfaceIdentity(
        entry_point="instrumentation-test", route_bindings=("/mcp",),
        transport_bindings=("in_process", "http", "stdio"),
        process_lifecycle_id="test", catalog_digest="catalog",
        scope_digest="scope", policy_digest="policy", closure_digest="closure",
    )
    return ServerCompositionPlan(identity, "flat", names)


def _handler(domain: str):
    @deterministic(input_model=InputDTO, output_model=OutputDTO)
    def execute(value: int) -> ToolResult[OutputDTO]:
        return ok(OutputDTO(domain=domain, value=value))
    return execute


@pytest.mark.asyncio
async def test_two_domains_publish_one_correlated_lifecycle_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    persisted: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    previous = get_service("tool_invocation_sink")
    set_service("tool_invocation_sink", lambda *args, **kwargs: persisted.append((args, kwargs)))
    class CallbackServer:
        def __init__(self, name: str, *, on_list_tools: Any, on_call_tool: Any) -> None:
            self.name = name
            self.on_list_tools = on_list_tools
            self.on_call_tool = on_call_tool

    monkeypatch.setattr("mcp.server.Server", CallbackServer)
    registrations = (
        NativeToolRegistration("security_scan", "", _handler("security"), "security", "scan"),
        NativeToolRegistration("wine_pair", "", _handler("wine"), "wine", "pair"),
    )
    server = NativeMCPV2Composer(
        _plan(frozenset(item.name for item in registrations)), registrations,
    ).compose()
    token = set_envelope({
        "correlation_id": "corr-744", "run_id": "run-744",
        "session_id": "session-744", "principal_id": "principal-744",
    })
    try:
        results = [
            await server.on_call_tool(None, SimpleNamespace(name=name, arguments={"value": 7}))
            for name in ("security_scan", "wine_pair")
        ]
    finally:
        reset_envelope(token)
        set_service("tool_invocation_sink", previous)

    assert [item.structured_content["data"]["domain"] for item in results] == ["security", "wine"]
    assert len(events) == 4
    for brick in ("security", "wine"):
        lifecycle = [item for item in events if item["brick"] == brick]
        assert [item["phase"] for item in lifecycle] == ["start", "result"]
        assert len({item["invocation_id"] for item in lifecycle}) == 1
        assert all(item["correlation_id"] == "corr-744" for item in lifecycle)
        assert all(item["workflow_run_id"] == "run-744" for item in lifecycle)
        assert all("parent_invocation_id" not in item for item in lifecycle)
    assert len(persisted) == 2


@pytest.mark.asyncio
async def test_direct_catalog_redacts_protected_values_and_preserves_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    catalog = ToolCatalog("integrations-brick")

    @catalog.tool(name="integrations_send_email")
    def send_email(body: str, subject: str) -> ToolResult[OutputDTO]:
        return ok(OutputDTO(domain="communications", value=1))

    canary = "protected-business-canary@example.test"
    result = await catalog.call_tool(
        "integrations_send_email", {"body": canary, "subject": canary},
    )
    assert result.structured_content["data"] == {"domain": "communications", "value": 1}
    assert [item["phase"] for item in events] == ["start", "result"]
    assert canary not in repr(events)
