"""Public-MCP-v2 low-level Server composer for typed flat MCP tools."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from .access_control import AccessControllerPort
from .native_v2_access import operation
from .native_v2_dispatch import dispatch_call
from .elicitation import PrepareCallable
from .server_surface import ServerCompositionPlan


@dataclass(frozen=True, slots=True)
class NativeToolRegistration:
    """A category-decorated typed handler admitted by one surface plan."""

    name: str
    description: str
    handler: Callable[..., Any]
    brick_name: str | None = None
    source_name: str | None = None
    prepare: PrepareCallable | None = None
    telemetry_excluded_argument_fields: frozenset[str] = frozenset()
    telemetry_excluded_envelope_fields: frozenset[str] = frozenset()

    def input_schema(self) -> dict[str, Any]:
        """Return the existing strict input DTO's flat JSON Schema."""
        model = getattr(self.handler, "_mcp_input_model", None)
        if model is None or not hasattr(model, "model_json_schema"):
            raise ValueError(f"{self.name} must have a typed MCP input model")
        schema = model.model_json_schema(mode="validation")
        if schema.get("type") != "object":
            raise ValueError(f"{self.name} input schema must be an object")
        return schema


class NativeMCPV2Composer:
    """Compose one public-v2 ``Server`` from an immutable surface plan."""

    def __init__(
        self,
        plan: ServerCompositionPlan,
        registrations: tuple[NativeToolRegistration, ...],
        access_controller: AccessControllerPort | None = None,
    ) -> None:
        names = tuple(item.name for item in registrations)
        if len(names) != len(set(names)):
            raise ValueError("native tool registrations must be unique")
        if frozenset(names) != plan.selected_tools:
            raise ValueError("registrations must exactly match selected tools")
        self._plan = plan
        self._registrations = registrations
        self._access_controller = access_controller
        self._server: Any | None = None

    @property
    def plan(self) -> ServerCompositionPlan:
        """Return the immutable plan bound to this one server instance."""
        return self._plan

    def compose(self) -> Any:
        """Build once with public ``Server(on_list_tools=, on_call_tool=)`` APIs."""
        if self._server is not None:
            return self._server
        try:
            from mcp.server import Server
            from mcp.types import ListToolsResult, TextContent, Tool
        except ImportError as exc:  # pragma: no cover - pre-cutover environment
            raise RuntimeError("NativeMCPV2Composer requires mcp>=2.1.1") from exc
        if not _supports_public_callbacks(Server):
            raise RuntimeError("NativeMCPV2Composer requires public MCP v2 callbacks")
        registrations = {item.name: item for item in self._registrations}
        tools = [
            Tool(name=item.name, description=item.description, input_schema=item.input_schema())
            for item in self._registrations
        ]

        async def list_tools(_: Any, __: Any) -> Any:
            if self._access_controller is None:
                return ListToolsResult(tools=tools)
            principal = self._access_controller.principal()
            if principal is None:
                return ListToolsResult(tools=[])
            visible = [
                tool for tool, item in zip(tools, self._registrations, strict=True)
                if self._access_controller.decide(
                    principal, operation(item, "discover"),
                ).allowed
            ]
            return ListToolsResult(tools=visible)

        async def call_tool(context: Any, params: Any) -> Any:
            return await dispatch_call(
                context, params, registrations, self._access_controller, TextContent,
            )

        self._server = Server(
            self._plan.identity.entry_point,
            on_list_tools=list_tools,
            on_call_tool=call_tool,
        )
        return self._server


def _supports_public_callbacks(server_type: type[Any]) -> bool:
    """Require the documented v2 constructor surface, never private fields."""
    try:
        parameters = inspect.signature(server_type).parameters
    except (TypeError, ValueError):
        return False
    return {"on_list_tools", "on_call_tool"}.issubset(parameters)


__all__ = ["NativeMCPV2Composer", "NativeToolRegistration"]
