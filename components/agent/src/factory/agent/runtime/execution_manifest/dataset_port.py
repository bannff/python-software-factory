"""Named MCP adapter for Dataset definition artifacts."""
from __future__ import annotations

import inspect
from typing import Any

from .ports import Invoker


class NamedDatasetMCPPort:
    """Calls Dataset only by its public MCP tool names."""

    def __init__(self, invoker: Invoker) -> None:
        self._invoker = invoker

    @staticmethod
    def _data(tool_name: str, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise RuntimeError(f"{tool_name} returned a non-object")
        if result.get("ok") is False or result.get("isError"):
            raise RuntimeError(f"{tool_name} failed: {result}")
        if isinstance(result.get("result"), dict):
            native = result["result"]
            if native.get("kind") != "tool":
                raise RuntimeError(f"{tool_name} returned invalid native transport")
            result = native.get("structured_content")
            if not isinstance(result, dict):
                raise RuntimeError(f"{tool_name} returned no structured content")
        if result.get("schema_version") == "v1":
            if result.get("ok") is not True:
                raise RuntimeError(f"{tool_name} failed: {result.get('error')}")
            result = result.get("data")
        elif "data" in result and isinstance(result.get("data"), dict):
            result = result["data"]
        if not isinstance(result, dict):
            raise RuntimeError(f"{tool_name} returned invalid data")
        return result

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._invoker(tool_name, arguments)
        if inspect.isawaitable(result):
            result = await result
        return self._data(tool_name, result)

    async def publish_definition(self, artifact_json: str) -> dict[str, Any]:
        return await self._call(
            "dataset_publish_definition_artifact", {"artifact_json": artifact_json},
        )

    async def resolve_definition(self, reference: dict[str, Any]) -> dict[str, Any]:
        return await self._call("dataset_resolve_definition_artifact", reference)


__all__ = ["NamedDatasetMCPPort"]
