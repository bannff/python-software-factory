"""Tests for framework-neutral brick tool collection."""

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.tool_result import ToolResult, ok
from pydantic import BaseModel, ConfigDict


class InputDTO(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    value: int


class OutputDTO(BaseModel):
    value: int


def test_catalog_preserves_typed_handler_and_metadata() -> None:
    catalog = ToolCatalog("probe")

    @catalog.tool(name="probe.echo", description="Echo")
    @deterministic(input_model=InputDTO, output_model=OutputDTO)
    def echo(value: int) -> ToolResult[OutputDTO]:
        return ok(OutputDTO(value=value))

    tool = catalog.tool_map()["probe.echo"]
    assert tool.fn is echo
    assert tool.description == "Echo"
    assert tool.tool_name == "probe.echo"
    assert tool.fn._mcp_input_model is InputDTO
    assert tool.fn._mcp_output_model is OutputDTO
    assert not hasattr(tool, "parameters")
    assert not hasattr(tool, "return_type")
    assert not hasattr(tool, "run")


def test_catalog_tool_excludes_registered_fields_from_telemetry_only(monkeypatch) -> None:
    import asyncio

    events = []
    received = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    catalog = ToolCatalog("sandbox-brick")

    @catalog.tool(
        name="sandbox.execute",
        telemetry_excluded_argument_fields=frozenset({"command"}),
    )
    def execute(command: str, cwd: str) -> dict[str, str]:
        received.append((command, cwd))
        return {"status": "ok"}

    command = "secret-bearing-command-canary"
    result = asyncio.run(catalog.call_tool(
        "sandbox.execute", {"command": command, "cwd": "/workspace"},
    ))

    assert received == [(command, "/workspace")]
    assert result.structured_content == {"status": "ok"}
    start = next(event for event in events if event["phase"] == "start")
    assert start["args_summary"] == {"cwd": "/workspace"}
    assert command not in repr(events)


def test_catalog_resources_and_prompts_preserve_native_contracts() -> None:
    import asyncio
    import json

    catalog = ToolCatalog("probe")

    @catalog.resource("probe://items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @catalog.prompt(name="inspect_item")
    def inspect_item(item_id: str, mode: str = "brief") -> str:
        return f"Inspect {item_id} in {mode} mode"

    templates = asyncio.run(catalog.list_resource_templates())
    assert [entry.uri_template for entry in templates] == ["probe://items/{item_id}"]
    body = asyncio.run(catalog.read_resource("probe://items/a-1"))
    assert json.loads(body.contents[0].content) == {"item_id": "a-1"}
    prompts = asyncio.run(catalog.list_prompts())
    assert [(arg.name, arg.required) for arg in prompts[0].arguments] == [
        ("item_id", True), ("mode", False),
    ]
    rendered = asyncio.run(catalog.render_prompt("inspect_item", {"item_id": "a-1"}))
    assert rendered.messages[0].content.text == "Inspect a-1 in brief mode"
