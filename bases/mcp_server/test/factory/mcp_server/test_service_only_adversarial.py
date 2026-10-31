"""Adversarial reentry tests for exact protected-wrapper permits."""
from __future__ import annotations

import asyncio

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    AttemptBinding, ServiceOnlyAccessError, ToolResult,
    mint_internal_invocation_claims, ok, operational,
    reset_internal_invocation_claims, service_only, set_internal_invocation_claims,
)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str
    mode: str


class _Output(BaseModel):
    changed: bool


def _args(mode: str) -> dict:
    return {
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 1,
        "manifest_digest": "a" * 64, "mode": mode,
    }


def _fixture():
    effects: list[str] = []
    blocked: list[str] = []
    delayed: list[asyncio.Task] = []
    gate: list[asyncio.Event] = []
    child = ToolCatalog("demo")

    @child.tool(name="demo_other")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    async def other(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, mode: str,
    ) -> ToolResult[_Output]:
        effects.append("other")
        return ok(_Output(changed=True))

    @child.tool(name="demo_protected")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    async def protected(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, mode: str,
    ) -> ToolResult[_Output]:
        effects.append(mode)

        async def direct(label: str, target=protected) -> None:
            try:
                await target(**_args("child"))
            except ServiceOnlyAccessError:
                blocked.append(label)

        if mode == "recursive":
            await direct("recursive")
        elif mode == "cross-wrapper":
            await direct("cross-wrapper", other)
        elif mode == "parallel":
            await asyncio.gather(
                asyncio.create_task(direct("parallel-1")),
                asyncio.create_task(direct("parallel-2")),
            )
        elif mode == "delayed":
            event = asyncio.Event()
            gate.append(event)

            async def later() -> None:
                await event.wait()
                await direct("delayed")

            delayed.append(asyncio.create_task(later()))
        return ok(_Output(changed=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child
    return aggregator, effects, blocked, delayed, gate


def _invoke(aggregator, mode: str) -> dict:
    return NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
        {"brick_name": "demo", "tool_name": "protected"},
        arguments=_args(mode), idempotency_key=f"attempt-{mode}",
        envelope={"run_id": "run-1"},
        attempt={
            "workflow_run_id": "run-1", "attempt_id": "attempt-1",
            "revision": 1, "manifest_digest": "a" * 64,
        },
    )


def test_recursion_cross_wrapper_and_parallel_child_tasks_fail() -> None:
    for mode, expected in (
        ("recursive", ["recursive"]),
        ("cross-wrapper", ["cross-wrapper"]),
        ("parallel", ["parallel-1", "parallel-2"]),
    ):
        aggregator, effects, blocked, _, _ = _fixture()
        result = _invoke(aggregator, mode)
        assert result["ok"] is True
        assert effects == [mode]
        assert sorted(blocked) == sorted(expected)


def test_delayed_inherited_task_fails_after_dispatch_closes() -> None:
    async def scenario() -> tuple[list[str], list[str]]:
        aggregator, effects, blocked, delayed, gate = _fixture()
        child, resolved, _ = aggregator.resolve_brick_tool("demo", "protected")
        tool = await child.get_tool(resolved)
        claims = mint_internal_invocation_claims(
            caller="workflow", audience="demo", target_tool=resolved,
            binding=AttemptBinding(
                workflow_run_id="run-1", attempt_id="attempt-1", revision=1,
                manifest_digest="a" * 64,
            ),
            target=tool,
        )
        token = set_internal_invocation_claims(claims)
        try:
            result = await aggregator.call_brick_tool(
                "demo", "protected", _args("delayed"),
            )
        finally:
            reset_internal_invocation_claims(token)
        assert result["ok"] is True
        gate[0].set()
        await delayed[0]
        return effects, blocked

    effects, blocked = asyncio.run(scenario())
    assert effects == ["delayed"]
    assert blocked == ["delayed"]
