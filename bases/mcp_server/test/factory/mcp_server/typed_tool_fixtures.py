"""Strict typed ToolCatalog fixtures for MCP-server public admission tests."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import ToolResult, ok, operational


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


class BoolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: bool


class ValueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


def add_empty_tool(catalog: Any, name: str) -> Callable[[], ToolResult[BoolOutput]]:
    """Register one admitted no-argument operational test tool."""
    @catalog.tool(name=name)
    @operational(input_model=EmptyInput, output_model=BoolOutput)
    def handler() -> ToolResult[BoolOutput]:
        return ok(BoolOutput(ok=True))

    return handler


def add_value_tool(catalog: Any, name: str) -> Callable[[str], ToolResult[ValueOutput]]:
    """Register one admitted string-argument operational test tool."""
    @catalog.tool(name=name)
    @operational(input_model=ValueInput, output_model=ValueOutput)
    def handler(value: str) -> ToolResult[ValueOutput]:
        return ok(ValueOutput(value=value))

    return handler
