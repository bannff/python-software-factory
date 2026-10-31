"""FE-side tool stubs for the Strands chat adapter (phase 1 sentinel port).

Strands has no per-invocation tool injection API — tool advertisement to
the LLM goes through the per-Agent ``ToolRegistry``, whose
``dynamic_tools`` dict is re-read on every model-prep call. The chat
adapter registers one stub per ``FrontendToolSpec`` for the duration of
the turn and unregisters it in a ``finally`` (the same register/
unregister cycle ``ChatAgentPort.stream`` documents).

The stub's ``stream`` coroutine is what runs when the LLM invokes the FE
tool. It yields exactly one sentinel ``ToolResult`` and sets
``request_state["stop_event_loop"]`` so the event loop halts cleanly
after the result — the CopilotKit FE handler runs browser-side and the
resume turn re-POSTs with the handler's reply.
"""
from __future__ import annotations

from typing import Any

from strands.types._events import ToolResultEvent
from strands.types.tools import AgentTool, ToolResult, ToolSpec, ToolUse

from ..models import FrontendToolSpec


def _wrap_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    """Thin parameter dicts go in a JSONSchema object envelope."""
    if (
        isinstance(parameters, dict)
        and parameters.get("type") == "object"
        and isinstance(parameters.get("properties"), dict)
    ):
        return parameters
    return {
        "type": "object",
        "properties": parameters if isinstance(parameters, dict) else {},
        "required": [],
    }


class _StubAgentTool(AgentTool):
    """Minimal ``AgentTool`` that defers execution to the FE handler."""

    def __init__(self, spec: FrontendToolSpec) -> None:
        super().__init__()
        self._spec = spec
        self._parameters = _wrap_parameters(spec.parameters)

    @property
    def tool_name(self) -> str:
        return self._spec.name

    @property
    def tool_spec(self) -> ToolSpec:
        return {
            "name": self._spec.name,
            "description": self._spec.description,
            "inputSchema": {"json": self._parameters},
        }

    @property
    def tool_type(self) -> str:
        return "frontend_stub"

    async def stream(  # type: ignore[override]
        self, tool_use: ToolUse, invocation_state: dict[str, Any], **_: Any,
    ) -> Any:
        tool_use_id = str(tool_use.get("toolUseId", ""))
        result: ToolResult = {
            "toolUseId": tool_use_id,
            "status": "success",
            "content": [{
                "json": {
                    "_frontend_pending": True,
                    "name": self._spec.name,
                    "args": tool_use.get("input", {}),
                },
            }],
        }
        # Halt the event loop AFTER this tool result — the FE handler runs
        # browser-side and the resume turn re-POSTs with its reply.
        request_state = invocation_state.setdefault("request_state", {})
        request_state["stop_event_loop"] = True
        yield ToolResultEvent(result)


def fe_stub_tool(spec: FrontendToolSpec) -> AgentTool:
    """Build one FE stub ``AgentTool`` from a validated registration."""
    return _StubAgentTool(spec)


def register_frontend_stubs(agent: Any, fe_tools: list[FrontendToolSpec] | None) -> list[Any]:
    """Register per-turn FE stubs; returns the tools to unregister."""
    if not fe_tools:
        return []
    registered = []
    for spec in fe_tools:
        tool = fe_stub_tool(spec)
        # Idempotent: a leftover prior-turn stub with the same name is
        # replaced rather than raising on the duplicate registration.
        agent.tool_registry.dynamic_tools.pop(tool.tool_name, None)
        agent.tool_registry.register_dynamic_tool(tool)
        registered.append(tool)
    return registered


def unregister_frontend_stubs(agent: Any, stubs: list[Any]) -> None:
    for tool in stubs:
        agent.tool_registry.dynamic_tools.pop(tool.tool_name, None)


__all__ = ["fe_stub_tool", "register_frontend_stubs", "unregister_frontend_stubs"]
