"""Real LangGraph approval-list suspend/resume integration."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import Field

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.approval_policy import InMemoryApprovalPolicyStore
from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
)
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class ToolCallModel(BaseChatModel):
    seen: list[list[Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "approval-test"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ToolCallModel":
        del tools, kwargs
        return self

    def _reply(self, messages: list[Any]) -> AIMessage:
        self.seen.append(list(messages))
        if not any(isinstance(item, ToolMessage) for item in messages):
            return AIMessage(content="", tool_calls=[{
                "name": "demo_tool", "args": {"value": "x"},
                "id": "model-call", "type": "tool_call",
            }])
        return AIMessage(content="Tool completed")

    def _generate(self, messages: list[Any], **kwargs: Any) -> ChatResult:
        del kwargs
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    def _stream(
        self, messages: list[Any], stop: list[str] | None = None,
        run_manager: Any = None, **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        del stop, run_manager, kwargs
        reply = self._reply(messages)
        if reply.tool_calls:
            call = reply.tool_calls[0]
            yield ChatGenerationChunk(message=AIMessageChunk(
                content="", tool_call_chunks=[{
                    "name": call["name"], "args": '{"value":"x"}',
                    "id": call["id"], "index": 0, "type": "tool_call_chunk",
                }]))
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=reply.content))


@pytest.mark.asyncio
async def test_listed_tool_pauses_then_approved_resume_invokes() -> None:
    calls: list[str] = []
    scope = CapabilityScope.create("approval", {"demo_tool"})

    async def handler(request):
        calls.append(request.arguments["value"])
        return CapabilityResult(content=({"type": "text", "text": "ok"},))

    client = InMemoryScopedCapabilityClient(
        scope,
        (CapabilityDescriptor("demo_tool", "demo", {
            "type": "object", "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }),),
        {"demo_tool": handler},
    )
    store = InMemoryApprovalPolicyStore()
    store.update("tenant", "owner", 0, tool_names=("demo_tool",))
    runtime = LangChainAgentRuntime(ToolCallModel(), client, approval_store=store)
    chat = LangChainChatAgent(runtime)

    first = [event async for event in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
    )]
    interrupt = next(event for event in first if event.type == "interrupt")
    assert calls == [] and interrupt.tool == "demo_tool"

    second = [event async for event in chat.stream(
        "approval-thread", "run tool", tenant_id="tenant", owner_id="owner",
        messages=[
            {"role": "user", "content": "run tool"},
            {"role": "tool", "toolCallId": interrupt.interrupt_id,
             "content": '{"approved":true,"tool":"demo_tool","command":"{}"}'},
        ],
    )]
    assert calls == ["x"]
    assert any(event.type == "text_delta" and event.content == "Tool completed"
               for event in second)
    await runtime.close()
