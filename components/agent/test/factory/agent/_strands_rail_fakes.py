"""Approval/steer fakes for the phase-2 rail tests (same-dir helper convention)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from strands.models.model import Model
from strands.types._events import ToolResultEvent
from strands.types.tools import AgentTool, ToolResult, ToolUse

from ._strands_contract_fakes import NullClient


class ApprovalRoundTripModel(Model):
    """Calls ``demo_tool`` on turn 1, finishes after the tool result.

    ``calls`` counts model invocations: the phase-2 resume contract is
    that the approved replay runs the pending toolUse WITHOUT a fresh
    model call, so the second stream still shows exactly 2 calls.
    """

    def __init__(self) -> None:
        super().__init__()
        self.config: dict[str, Any] = {}
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model: Any, prompt: Any, **kwargs: Any) -> AsyncIterator[dict]:
        yield {}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any,
    ) -> AsyncIterator[dict]:
        self.calls += 1
        has_tool_result = any(
            isinstance(block, dict) and "toolResult" in block
            for message in messages for block in message.get("content", ())
        )
        if not has_tool_result:
            tool_use: dict[str, Any] = {
                "toolUseId": "approval-call-1", "name": "demo_tool", "input": {"value": "x"},
            }
            yield {"contentBlockStart": {"start": {"toolUse": tool_use}, "contentBlockIndex": 0}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"value":"x"}'}}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        yield {"contentBlockDelta": {"delta": {"text": "Tool completed"}, "contentBlockIndex": 0}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class SteerCountingModel(Model):
    """Records the message blocks each model call sees."""

    def __init__(self) -> None:
        super().__init__()
        self.config: dict[str, Any] = {}
        self.seen: list[list[tuple[str, Any]]] = []

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model: Any, prompt: Any, **kwargs: Any) -> AsyncIterator[dict]:
        yield {}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any,
    ) -> AsyncIterator[dict]:
        self.seen.append([
            (message.get("role", ""), tuple(
                block.get("text", "") for block in message.get("content", ())
                if isinstance(block, dict)
            ))
            for message in messages
        ])
        yield {"contentBlockDelta": {"delta": {"text": "ok"}, "contentBlockIndex": 0}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class RecordingTool(AgentTool):
    """Real ``AgentTool`` recording executed toolUseIds; result content "x"."""

    def __init__(self) -> None:
        super().__init__()
        self.ran: list[str] = []

    @property
    def tool_name(self) -> str:
        return "demo_tool"

    @property
    def tool_spec(self) -> dict[str, Any]:
        return {
            "name": "demo_tool", "description": "demo",
            "inputSchema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        }

    @property
    def tool_type(self) -> str:
        return "python"

    async def stream(self, tool_use: ToolUse, invocation_state: dict[str, Any], **kwargs: Any) -> Any:
        self.ran.append(str(tool_use.get("toolUseId", "")))
        yield self.result_tool_use(tool_use)


__all__ = ["ApprovalRoundTripModel", "RecordingTool", "SteerCountingModel", "approval_chat"]


def approval_chat() -> Any:
    """Build the approval-rail chat fixture.

    Returns ``(chat, model, ctx)`` where ``ctx['seed']()`` seeds the
    listed-tool agent and ``ctx['ran']`` records executed toolUseIds.
    Shared so rail tests use the exact same wiring.
    """
    from factory.agent.runtime.adapters.strands_approval_rail import StrandsApprovalRail
    from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent
    from factory.agent.runtime.approval_policy import InMemoryApprovalPolicyStore
    from factory.mcp_utils.runtime.scoped_capabilities import (
        CapabilityDescriptor, CapabilityResult, CapabilityScope,
    )

    tool = RecordingTool()

    class DemoClient(NullClient):
        scope = CapabilityScope.create("strands-chat-test", {"demo_tool"})

        async def list_capabilities(self) -> tuple[Any, ...]:
            return (CapabilityDescriptor("demo_tool", "demo", {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }),)

        async def invoke(self, request: Any) -> Any:
            return CapabilityResult(
                content=({"type": "text", "text": request.arguments["value"]},),
            )

    ran = tool.ran
    store = InMemoryApprovalPolicyStore()
    store.update("tenant", "owner", 0, tool_names=("demo_tool",))
    model = ApprovalRoundTripModel()

    async def build() -> Any:
        from strands import Agent
        return Agent(
            agent_id="companion-x-default", name="approval-thread",
            system_prompt="test", model=model, tools=[tool],
            callback_handler=None,
            hooks=[StrandsApprovalRail(store)],
        )

    chat = StrandsChatAgent(DemoClient(), lambda _mid, **_kw: model,
                            model_id="fake", approval_store=store)

    async def seed() -> None:
        await chat._threads.get_or_build("approval-thread", "companion-x-default", build)

    return chat, model, {"ran": ran, "seed": seed}
