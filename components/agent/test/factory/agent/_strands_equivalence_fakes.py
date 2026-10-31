"""Shared fakes for the Strands/LangChain equivalence + contract tests.

Split from the test files so each stays under the 200-LOC tenet; the
scenarios (plain turn / tool turn / FE sentinel / cancel) and their
assertions stay in the tests. Same-dir import via ``from .`` works under
the repo's ``--import-mode=importlib`` + package-``__init__`` layout.

Two fake families live here: the equivalence fakes (LangChain vs Strands
scenario parity) and the chat-adapter contract fakes (``RepliedModel``
scenario switch, ``NullClient``).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

pytest.importorskip("langchain")

from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent
from factory.agent.runtime.models import FrontendToolSpec
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
)
from strands.models.model import Model

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

FE_SPEC = FrontendToolSpec(
    name="fe_navigate_canvas",
    description="Switch canvas",
    parameters={
        "type": "object",
        "properties": {"view": {"type": "string"}},
        "required": ["view"],
    },
)


def _langchain_client() -> InMemoryScopedCapabilityClient:
    async def _echo(request: Any) -> CapabilityResult:
        return CapabilityResult(content=({"type": "text", "text": request.arguments["value"]},))

    return InMemoryScopedCapabilityClient(
        CapabilityScope.create("equiv-test", {"echo"}),
        (CapabilityDescriptor("echo", "Echo one value", {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        }),),
        {"echo": _echo},
    )


class LangChainFakeModel(BaseChatModel):
    use_tool: bool = False
    frontend_call: bool = False

    @property
    def _llm_type(self) -> str:
        return "equiv-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "LangChainFakeModel":
        del tools, kwargs
        return self

    def _reply(self, messages: list[Any]) -> AIMessage:
        if self.use_tool and not any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="", tool_calls=[{
                "name": "echo", "args": {"value": "scoped"},
                "id": "call-1", "type": "tool_call",
            }])
        if self.frontend_call and not any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content="", tool_calls=[{
                "name": "fe_navigate_canvas", "args": {"view": "timeline-v2"},
                "id": "fe-call-1", "type": "tool_call",
            }])
        return AIMessage(content="humans reply")

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
                    "name": call["name"], "args": '{"value":"scoped"}' if self.use_tool else '{"view":"timeline-v2"}',
                    "id": call["id"], "index": 0, "type": "tool_call_chunk",
                }],
            ))
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=reply.content))


class StrandsFakeModel(Model):
    """Emits the same scenario shapes through the Bedrock-style stream."""

    use_tool: bool = False
    frontend_call: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        self.config = {}
        self.use_tool = kwargs.get("use_tool", False)
        self.frontend_call = kwargs.get("frontend_call", False)

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model: Any, prompt: Any, **kwargs: Any) -> AsyncIterator[dict]:
        yield {}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any,
    ) -> AsyncIterator[dict]:
        if not self.use_tool and not self.frontend_call:
            yield {"contentBlockDelta": {"delta": {"text": "humans reply"}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        if not any(
            isinstance(block, dict) and "toolResult" in block
            for message in messages for block in message.get("content", ())
        ):
            tool_use = {
                "toolUseId": "fe-call-1" if self.frontend_call else "call-1",
                "name": "fe_navigate_canvas" if self.frontend_call else "echo",
                "input": {},
            }
            yield {"contentBlockStart": {"start": {"toolUse": tool_use}, "contentBlockIndex": 0}}
            if self.frontend_call:
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"view":"timeline-v2"}'}}, "contentBlockIndex": 0}}
            else:
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"value":"scoped"}'}}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": "humans reply"}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}


class StrandsSlowModel(Model):
    """Streams one chunk then blocks until cancelled."""

    def __init__(self, gate: asyncio.Event) -> None:
        super().__init__()
        self.config = {}
        self._gate = gate

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model: Any, prompt: Any, **kwargs: Any) -> AsyncIterator[dict]:
        yield {}

    async def stream(self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any) -> AsyncIterator[dict]:
        yield {"contentBlockDelta": {"delta": {"text": "partial"}, "contentBlockIndex": 0}}
        await self._gate.wait()
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}


def _langchain_agent(model: LangChainFakeModel) -> LangChainChatAgent:
    return LangChainChatAgent(LangChainAgentRuntime(model, _langchain_client()))


def _strands_agent(model: Model) -> StrandsChatAgent:
    return StrandsChatAgent(_langchain_client(), lambda _model_id, **_kw: model, model_id="fake")
