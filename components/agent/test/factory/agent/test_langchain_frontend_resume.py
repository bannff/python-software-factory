"""Regression coverage for LangGraph-native CopilotKit frontend tool resume."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import Field

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.models import FrontendToolSpec
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class FrontendCallModel(BaseChatModel):
    """Calls one browser tool, then answers only after its ToolMessage."""

    seen: list[list[Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "frontend-call-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> FrontendCallModel:
        del tools, kwargs
        return self

    def _reply(self, messages: list[Any]) -> AIMessage:
        self.seen.append(list(messages))
        if not any(isinstance(item, ToolMessage) for item in messages):
            return AIMessage(content="", tool_calls=[{
                "name": "fe_navigate_canvas",
                "args": {"view": "timeline-v2"},
                "id": "fe-call-1",
                "type": "tool_call",
            }])
        return AIMessage(content="Timeline opened")

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
                content="",
                tool_call_chunks=[{
                    "name": call["name"], "args": '{"view":"timeline-v2"}',
                    "id": call["id"], "index": 0, "type": "tool_call_chunk",
                }],
            ))
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=reply.content))


def _chat(model: FrontendCallModel) -> tuple[LangChainAgentRuntime, LangChainChatAgent]:
    client = InMemoryScopedCapabilityClient(
        CapabilityScope.create("frontend-test", set()), (), {},
    )
    runtime = LangChainAgentRuntime(model, client)
    return runtime, LangChainChatAgent(runtime)


def _spec() -> FrontendToolSpec:
    return FrontendToolSpec(
        name="fe_navigate_canvas",
        description="Switch canvas",
        parameters={
            "type": "object",
            "properties": {"view": {"type": "string"}},
            "required": ["view"],
        },
    )


@pytest.mark.asyncio
async def test_frontend_tool_interrupts_then_resumes_from_browser_result() -> None:
    model = FrontendCallModel()
    runtime, chat = _chat(model)
    first = [event async for event in chat.stream(
        "frontend-thread", "open timeline", fe_tools=[_spec()],
        messages=[{"role": "user", "content": "open timeline"}],
    )]
    assert [event.type for event in first] == [
        "tool_call_delta", "tool_result", "done",
    ]
    assert first[1].payload["_frontend_pending"] is True
    assert first[1].tool_call_id == "fe-call-1"

    resumed_messages = [
        {"role": "user", "content": "open timeline"},
        {"role": "tool", "toolCallId": "fe-call-1",
         "content": '{"success":true,"view":"timeline-v2"}'},
    ]
    second = [event async for event in chat.stream(
        "frontend-thread", "open timeline", fe_tools=[_spec()],
        messages=resumed_messages,
    )]
    assert [event.type for event in second] == ["tool_result", "text_delta", "done"]
    assert second[1].content == "Timeline opened"
    tool_messages = [
        item
        for turn in model.seen
        for item in turn
        if isinstance(item, ToolMessage)
    ]
    assert tool_messages
    assert json.loads(tool_messages[-1].content) == {
        "success": True, "view": "timeline-v2",
    }
    await runtime.close()

class EmptyThenFrontendModel(FrontendCallModel):
    attempts: int = 0

    def _reply(self, messages: list[Any]) -> AIMessage:
        self.attempts += 1
        if self.attempts == 1:
            return AIMessage(content="")
        return super()._reply(messages)


@pytest.mark.asyncio
async def test_empty_first_response_retries_once_and_reaches_frontend_tool() -> None:
    model = EmptyThenFrontendModel()
    runtime, chat = _chat(model)
    events = [event async for event in chat.stream(
        "empty-retry-thread", "open timeline", fe_tools=[_spec()],
        messages=[{"role": "user", "content": "open timeline"}],
    )]
    assert model.attempts == 2
    assert [event.type for event in events] == [
        "tool_call_delta", "tool_result", "done",
    ]
    assert events[1].payload["_frontend_pending"] is True
    await runtime.close()
