"""Operational Config MCP tools with strict local DTO boundaries."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, ok, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    DeleteInput, DeleteOutput, GetAllOutput, GetInput, GetOutput, GetTypedInput,
    GetTypedOutput, KeysOutput, PrefixInput, SetInput, SetOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import ConfigRuntime


def register(mcp: Any, get_runtime: Callable[[], "ConfigRuntime"]) -> None:
    """Register stateful tools while preserving flat public kwargs and defaults."""

    @typed_tool(mcp)
    @operational(input_model=GetInput, output_model=GetOutput)
    def config_get(key: str, default: str | None = None) -> ToolResult[GetOutput]:
        """Get a configuration value."""
        value = get_runtime().get_config().get(key, default)
        return ok(GetOutput(key=key, value=value, found=value is not None and value != default))

    @typed_tool(mcp)
    @operational(input_model=SetInput, output_model=SetOutput)
    def config_set(key: str, value: str) -> ToolResult[SetOutput]:
        """Set a configuration value."""
        return ok(SetOutput(key=key, success=get_runtime().get_config().set(key, value)))

    @typed_tool(mcp)
    @operational(input_model=DeleteInput, output_model=DeleteOutput)
    def config_delete(key: str) -> ToolResult[DeleteOutput]:
        """Delete a configuration key."""
        return ok(DeleteOutput(key=key, deleted=get_runtime().get_config().delete(key)))

    @typed_tool(mcp)
    @operational(input_model=PrefixInput, output_model=KeysOutput)
    def config_keys(prefix: str = "") -> ToolResult[KeysOutput]:
        """List configuration keys with an optional prefix filter."""
        keys = get_runtime().get_config().keys(prefix)
        return ok(KeysOutput(prefix=prefix, keys=keys, count=len(keys)))

    @typed_tool(mcp)
    @operational(input_model=PrefixInput, output_model=GetAllOutput)
    def config_get_all(prefix: str = "") -> ToolResult[GetAllOutput]:
        """Get all configuration values with an optional prefix filter."""
        values = get_runtime().get_config().get_all(prefix)
        return ok(GetAllOutput(prefix=prefix, values=values, count=len(values)))

    @typed_tool(mcp)
    @operational(input_model=GetTypedInput, output_model=GetTypedOutput)
    def config_get_typed(
        key: str, value_type: str = "str", default: str | None = None,
    ) -> ToolResult[GetTypedOutput]:
        """Get a value using legacy type labels and fallback semantics."""
        type_map = {"str": str, "int": int, "bool": bool, "float": float}
        target_type = type_map.get(value_type, str)
        parsed_default = None
        if default is not None:
            try:
                parsed_default = (default.lower() in ("true", "1", "yes")
                                  if target_type is bool else target_type(default))
            except (ValueError, AttributeError):
                parsed_default = None
        value = get_runtime().get_config().get_typed(key, target_type, parsed_default)
        return ok(GetTypedOutput(
            key=key, value=value, type=value_type,
            found=value is not None and value != parsed_default,
        ))
