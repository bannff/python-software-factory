"""Strict DTOs for the MCP aggregator's public FastMCP boundary."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ConfigDict, RootModel

F = TypeVar("F", bound=Callable[..., Any])


class DTO(BaseModel):
    """Strict flat ingress shared only by this base's public tools."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat input for tools without arguments."""


class BrickInput(DTO):
    brick_name: str


class ResourceInput(BrickInput):
    uri: str


class PromptInput(BrickInput):
    prompt_name: str
    arguments: str | None = None


class CallBrickToolInput(BrickInput):
    tool_name: str
    arguments: str | None = None
    envelope: str | None = None
    as_task: bool = False
    task_ttl_ms: int | None = None


class CatalogInput(DTO):
    categories: list[str] | None = None


class JsonObjectOutput(RootModel[dict[str, Any]]):
    """A JSON object payload whose existing keys remain transport-owned."""


class NativeTransportOutput(JsonObjectOutput):
    """The aggregator's existing call transport success/failure envelope."""


def native_transport_egress(*, output_model: type[BaseModel]) -> Callable[[F], F]:
    """Declare the sole raw transport egress without applying ``ToolResult``.

    ``call_brick_tool`` transports either a task payload or the invoked tool's
    native envelope. Wrapping it would add an outer result layer and break the
    aggregator's public protocol. Foreman recognizes this marker only for that
    one MCP-server tool while still validating its same-base DTO declaration.
    """
    if not issubclass(output_model, BaseModel):
        raise TypeError("native transport output_model must be a Pydantic model")

    def decorate(func: F) -> F:
        setattr(func, "_mcp_output_model", output_model)
        setattr(func, "_mcp_native_transport_egress", True)
        return func

    return decorate
