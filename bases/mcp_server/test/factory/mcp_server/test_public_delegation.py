"""Public delegation admission and credential telemetry canaries."""
from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_meta import build_native_meta_catalog
from factory.mcp_utils.interface import (
    ToolResult, get_service, ok, operational, service_only, set_service,
)
from factory.mcp_utils.runtime.tool_catalog import CatalogTool, ToolCatalog


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    api_key: str
    nested: dict[str, Any]


class OutputDTO(BaseModel):
    secret: str
    nested: dict[str, Any]


def _typed(fn):
    return operational(input_model=InputDTO, output_model=OutputDTO)(fn)


def _aggregator() -> tuple[MCPAggregator, list[str]]:
    effects: list[str] = []
    catalog = ToolCatalog("demo")

    @_typed
    def success(api_key: str, nested: dict[str, Any]) -> ToolResult[OutputDTO]:
        effects.append("success")
        return ok(OutputDTO(secret=api_key, nested=nested))

    @_typed
    def failure(api_key: str, nested: dict[str, Any]) -> ToolResult[OutputDTO]:
        effects.append("failure")
        raise RuntimeError(f"failed with {api_key} and {nested}")

    @_typed
    def hidden(api_key: str, nested: dict[str, Any]) -> ToolResult[OutputDTO]:
        effects.append("hidden")
        return ok(OutputDTO(secret=api_key, nested=nested))

    hidden = service_only(callers={"workflow"}, binding="attempt")(hidden)
    first = _typed(lambda api_key, nested: ok(OutputDTO(secret=api_key, nested=nested)))
    second = _typed(lambda api_key, nested: ok(OutputDTO(secret=api_key, nested=nested)))
    for name, handler in (
        ("demo_success", success), ("demo_failure", failure),
        ("demo_hidden", hidden), ("demo.echo", first), ("demo_echo", second),
        ("demo_invalid", lambda **_: effects.append("invalid")),
    ):
        catalog.add_tool(CatalogTool(name, "", handler))
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    return aggregator, effects


@pytest.mark.asyncio
async def test_service_only_and_nonexistent_are_indistinguishable_and_effect_free() -> None:
    aggregator, effects = _aggregator()
    arguments = {"api_key": "secret", "nested": {}}
    hidden = await aggregator.call_public_brick_tool("demo", "hidden", arguments)
    missing = await aggregator.call_public_brick_tool("demo", "not_real", arguments)
    assert hidden == missing == {
        "ok": False,
        "error": {"type": "ToolNotFoundError", "message": "tool_not_found"},
    }
    assert effects == []


@pytest.mark.asyncio
async def test_invalid_and_collision_targets_cannot_be_delegated() -> None:
    aggregator, effects = _aggregator()
    arguments = {"api_key": "secret", "nested": {}}
    results = [
        await aggregator.call_public_brick_tool("demo", name, arguments)
        for name in ("invalid", "echo", "demo.echo", "demo_echo")
    ]
    assert {result["error"]["type"] for result in results} == {"ToolNotFoundError"}
    assert {result["error"]["message"] for result in results} == {"tool_not_found"}
    assert effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["success", "failure"])
async def test_delegated_events_and_sink_never_capture_credentials(
    target: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregator, effects = _aggregator()
    events: list[dict[str, Any]] = []
    persisted: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    previous = get_service("tool_invocation_sink")
    set_service("tool_invocation_sink", lambda *args, **kwargs: persisted.append((args, kwargs)))
    canary = f"delegated-{target}-credential-canary"
    arguments = {
        "api_key": canary,
        "nested": {"authorization": canary, "route": "public-delegation"},
    }
    try:
        result = await aggregator.call_public_brick_tool("demo", target, arguments)
    finally:
        set_service("tool_invocation_sink", previous)
    assert effects == [target]
    assert canary not in repr(events)
    assert canary not in repr(persisted)
    assert all(event["args_summary"] == {
        "nested": {"route": "public-delegation"},
    } for event in events)
    if target == "success":
        assert canary in repr(result)
        assert all(event["result_summary"]["status"] == "ok" for event in events[1:])
    else:
        assert result["ok"] is True
        assert result["result"]["structured_content"]["ok"] is False
        assert canary not in repr(result)
        assert events[-1]["result_summary"]["status"] == "error"


@pytest.mark.asyncio
async def test_native_meta_call_uses_public_delegate() -> None:
    class Stub:
        async def call_public_brick_tool(self, brick, tool, arguments):
            return {"brick": brick, "tool": tool, "arguments": arguments}

        async def call_brick_tool(self, *_args, **_kwargs):
            raise AssertionError("raw dispatch must not be used")

    result = await build_native_meta_catalog(Stub()).call_tool(
        "call_brick_tool", {
            "brick_name": "demo", "tool_name": "safe",
            "arguments": json.dumps({"value": 1}),
        },
    )
    assert result.structured_content["data"]["tool"] == "safe"
