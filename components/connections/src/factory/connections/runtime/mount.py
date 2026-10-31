"""Project one registered external MCP server into a synthetic ``ToolCatalog``.

Mounted as a pseudo-brick in the gateway aggregator, so progressive discovery,
``MCP_INCLUDE_BRICKS`` scoping, the approval list, telemetry spans, and the
Agent's tool projection all apply to external tools unchanged.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityInvocation, ToolCatalog, ToolResult, ok,
    operational,
)

from .adapters.http_source import discover_tools, http_source, resolve_headers
from .adapters.stdio_source import StdioToolSource, child_environment
from .models import ServerRecord

BRICK_PREFIX = "mcp-"
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class RemoteToolOutput(BaseModel):
    """Remote MCP result projected verbatim (content + structured content)."""

    model_config = ConfigDict(extra="forbid")
    content: list[dict[str, Any]]
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


def brick_name(server_name: str) -> str:
    return f"{BRICK_PREFIX}{server_name}"


async def open_source(record: ServerRecord) -> tuple[Any, tuple[CapabilityDescriptor, ...]]:
    """Dial the server once and return (long-lived source, discovered tools)."""
    spec = record.spec
    if spec.transport == "stdio":
        source = StdioToolSource(
            spec.command or "", tuple(spec.args), cwd=spec.cwd, env=child_environment(spec.env),
        )
        return source, await source.list_capabilities()
    tools = await discover_tools(spec.url or "", resolve_headers(spec.headers))
    return http_source(
        record.name, spec.url or "", spec.headers, tuple(tool.name for tool in tools),
    ), tools


def build_catalog(
    record: ServerRecord, source: Any, tools: tuple[CapabilityDescriptor, ...],
) -> ToolCatalog:
    """One proxy tool per remote tool, carrying the remote's own input schema."""
    catalog = ToolCatalog(brick_name(record.name))
    for tool in tools:
        if not _TOOL_NAME.fullmatch(tool.name):
            continue
        catalog.tool(name=tool.name, description=tool.description)(
            _proxy(record.name, tool, source),
        )
    return catalog


def _input_model(server: str, tool: CapabilityDescriptor) -> type[BaseModel]:
    schema = dict(tool.input_schema or {})
    schema.setdefault("type", "object")
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = set(schema.get("required") or ()) if isinstance(schema.get("required"), list) else set()
    fields: dict[str, Any] = {
        name: (Any, Field(...) if name in required else Field(default=None))
        for name in properties
    }
    model = create_model(  # type: ignore[call-overload]
        f"Remote_{re.sub(r'[^A-Za-z0-9_]', '_', server)}_{re.sub(r'[^A-Za-z0-9_]', '_', tool.name)}",
        __config__=ConfigDict(extra="allow", json_schema_extra=lambda s: s.update(
            {key: value for key, value in schema.items() if key not in ("title",)},
        )),
        **fields,
    )
    return model


def _proxy(server: str, tool: CapabilityDescriptor, source: Any):
    input_model = _input_model(server, tool)

    @operational(input_model=input_model, output_model=RemoteToolOutput, idempotent=False)
    async def remote_tool(**arguments: Any) -> ToolResult[RemoteToolOutput]:
        result = await source.invoke(CapabilityInvocation(
            name=tool.name, arguments={k: v for k, v in arguments.items() if v is not None},
            idempotency_key=f"connections:{server}:{tool.name}",
        ))
        return ok(RemoteToolOutput(
            content=[dict(item) for item in result.content],
            structured_content=result.structured_content, is_error=result.is_error,
        ))

    remote_tool.__name__ = tool.name
    remote_tool.__doc__ = tool.description
    return remote_tool


__all__ = ["BRICK_PREFIX", "RemoteToolOutput", "brick_name", "build_catalog", "open_source"]
