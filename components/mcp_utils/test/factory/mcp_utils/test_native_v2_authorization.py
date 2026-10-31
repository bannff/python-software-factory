from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import (
    AccessDecision, AccessPrincipal, NativeMCPV2Composer, NativeToolRegistration,
    ServerCompositionPlan, ServerSurfaceIdentity, ToolResult, get_envelope, ok, operational,
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claimed_principal: str | None = None


class Output(BaseModel):
    observed: str | None


class Controller:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.principal_value = AccessPrincipal(
            subject="server-principal", client_id="client", tenant_id="tenant",
        )

    def principal(self):
        return self.principal_value

    def decide(self, _principal, _operation):
        return AccessDecision(allowed=self.allowed, reason="test-policy")


class CallbackServer:
    def __init__(self, _name, *, on_list_tools, on_call_tool):
        self.on_list_tools, self.on_call_tool = on_list_tools, on_call_tool


def _server(controller: Controller, effects: list[str]):
    @operational(input_model=Input, output_model=Output)
    async def effect(claimed_principal: str | None = None) -> ToolResult[Output]:
        del claimed_principal
        await asyncio.sleep(0)
        observed = (get_envelope() or {}).get("principal_id")
        effects.append(str(observed))
        return ok(Output(observed=observed))

    identity = ServerSurfaceIdentity(
        entry_point="test", route_bindings=("/mcp",), transport_bindings=("http",),
        process_lifecycle_id="test", catalog_digest="a", scope_digest="b",
        policy_digest="c", closure_digest="d",
    )
    plan = ServerCompositionPlan(identity, "flat", frozenset({"demo_effect"}))
    with patch("mcp.server.Server", CallbackServer):
        return NativeMCPV2Composer(
            plan, (NativeToolRegistration(
                "demo_effect", "", effect, brick_name="demo", source_name="effect",
            ),), access_controller=controller,
        ).compose()


async def _call(server, claimed: str = "attacker"):
    return await server.on_call_tool(None, SimpleNamespace(
        name="demo_effect", arguments={"claimed_principal": claimed},
    ))


def test_discovery_and_denial_fail_closed_before_effect() -> None:
    effects: list[str] = []
    controller = Controller(allowed=False)
    server = _server(controller, effects)
    listed = asyncio.run(server.on_list_tools(None, None))
    result = asyncio.run(_call(server))
    assert listed.tools == []
    assert result.is_error and effects == []
    assert "principal" not in repr(result).lower()


def test_server_principal_overrides_spoof_and_context_is_cleaned() -> None:
    effects: list[str] = []
    server = _server(Controller(), effects)
    result = asyncio.run(_call(server))
    assert result.structured_content["data"]["observed"] == "server-principal"
    assert effects == ["server-principal"] and get_envelope() is None


def test_concurrent_calls_do_not_leak_context() -> None:
    effects: list[str] = []
    server = _server(Controller(), effects)

    async def run():
        await asyncio.gather(*(_call(server, str(i)) for i in range(20)))

    asyncio.run(run())
    assert effects == ["server-principal"] * 20
    assert get_envelope() is None
