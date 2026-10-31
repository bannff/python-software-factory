"""Progressive native MCP-v2 meta-tools for concierge agents."""

from __future__ import annotations

import json
from typing import Any

from factory.mcp_utils.interface import (
    deterministic, operational, ToolCatalog, ToolResult, ok,
)

from .mcp_contracts import (
    BrickInput, CallBrickToolInput, EmptyInput, JsonObjectOutput,
    PromptInput, ResourceInput,
)

META_TOOL_NAMES = frozenset({
    "list_bricks", "get_brick_tools", "get_brick_resources",
    "get_brick_prompts", "call_brick_tool", "read_brick_resource",
    "render_brick_prompt", "get_tool_catalog", "reload_capabilities",
})


def build_native_meta_catalog(aggregator: Any) -> ToolCatalog:
    """Build the small progressive surface with full factory reach."""
    catalog = ToolCatalog("factory-mcp-meta")

    @catalog.tool()
    @deterministic(input_model=EmptyInput, output_model=JsonObjectOutput)
    def list_bricks() -> ToolResult[JsonObjectOutput]:
        return ok(aggregator.list_bricks())

    @catalog.tool()
    @deterministic(input_model=BrickInput, output_model=JsonObjectOutput)
    def get_brick_tools(brick_name: str) -> ToolResult[JsonObjectOutput]:
        return ok(aggregator.get_brick_tools(brick_name))

    @catalog.tool()
    @deterministic(input_model=BrickInput, output_model=JsonObjectOutput)
    def get_brick_resources(brick_name: str) -> ToolResult[JsonObjectOutput]:
        return ok(aggregator.get_brick_resources(brick_name))

    @catalog.tool()
    @deterministic(input_model=BrickInput, output_model=JsonObjectOutput)
    def get_brick_prompts(brick_name: str) -> ToolResult[JsonObjectOutput]:
        return ok(aggregator.get_brick_prompts(brick_name))

    @catalog.tool()
    @operational(input_model=CallBrickToolInput, output_model=JsonObjectOutput)
    async def call_brick_tool(
        brick_name: str, tool_name: str, arguments: str | None = None,
        envelope: str | None = None, as_task: bool = False,
        task_ttl_ms: int | None = None,
    ) -> ToolResult[JsonObjectOutput]:
        del as_task, task_ttl_ms
        if envelope is not None:
            return fail("authorization_denied")
        parsed = json.loads(arguments) if arguments else {}
        if not isinstance(parsed, dict):
            raise ValueError("tool arguments must be a JSON object")
        return ok(await aggregator.call_public_brick_tool(
            brick_name, tool_name, parsed,
        ))

    @catalog.tool()
    @deterministic(input_model=ResourceInput, output_model=JsonObjectOutput)
    async def read_brick_resource(
        brick_name: str, uri: str,
    ) -> ToolResult[JsonObjectOutput]:
        return ok(await aggregator.read_brick_resource(brick_name, uri))

    @catalog.tool()
    @deterministic(input_model=PromptInput, output_model=JsonObjectOutput)
    async def render_brick_prompt(
        brick_name: str, prompt_name: str, arguments: str | None = None,
    ) -> ToolResult[JsonObjectOutput]:
        parsed = json.loads(arguments) if arguments else None
        return ok(await aggregator.render_brick_prompt(
            brick_name, prompt_name, parsed,
        ))

    @catalog.tool()
    @operational(input_model=EmptyInput, output_model=JsonObjectOutput, idempotent=False)
    async def reload_capabilities() -> ToolResult[JsonObjectOutput]:
        """Re-discover bricks, Agent registries, and external MCP servers without a restart."""
        from .capability_reload import reload_capabilities as run_reload
        return ok(await run_reload(aggregator))

    from .tool_catalog import register_catalog_tool
    register_catalog_tool(catalog, aggregator)
    return catalog


__all__ = ["META_TOOL_NAMES", "build_native_meta_catalog"]
