"""Injected ports used by immutable manifest storage and execution."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .descriptors import ToolDescriptor


class DatasetDefinitionPort(Protocol):
    async def publish_definition(self, artifact_json: str) -> dict[str, Any]: ...
    async def resolve_definition(self, reference: dict[str, Any]) -> dict[str, Any]: ...


class EvidenceSink(Protocol):
    async def persist(
        self, sequence: int, event: dict[str, Any], *, terminal: bool,
    ) -> None: ...


class ToolFactory(Protocol):
    def build_tools(self, descriptor: ToolDescriptor) -> list[Any]: ...


Invoker = Callable[[str, dict[str, Any]], Awaitable[Any] | Any]


__all__ = ["DatasetDefinitionPort", "EvidenceSink", "Invoker", "ToolFactory"]
