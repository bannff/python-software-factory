"""Metadata-only policy helpers for non-public MCP tools."""
from __future__ import annotations

from typing import Any, Mapping
from factory.mcp_utils.interface import is_service_only


def public_tool_map(tools: Mapping[str, Any]) -> dict[str, Any]:
    return {name: tool for name, tool in tools.items() if not is_service_only(tool)}


def public_tool_names(tools: Mapping[str, Any]) -> list[str]:
    return list(public_tool_map(tools))


__all__ = ["public_tool_map", "public_tool_names"]
