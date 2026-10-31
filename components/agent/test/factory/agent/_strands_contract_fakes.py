"""Chat-adapter contract fakes (scenario-switch model + null client).

Split from ``test_strands_chat_adapter.py`` (LOC tenet); shares the
same-dir helper convention with ``_strands_equivalence_fakes``.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from factory.agent.runtime.adapters.strands_chat import StrandsChatAgent
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from strands.models.model import Model


class RepliedModel(Model):
    """Configurable single-scenario fake over the Bedrock-style stream."""

    scenario: str = "plain"

    def __init__(self, scenario: str = "plain") -> None:
        super().__init__()
        self.config = {}
        self.scenario = scenario

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model: Any, prompt: Any, **kwargs: Any) -> AsyncIterator[dict]:
        yield {}

    def _called(self, messages: Any) -> bool:
        return any(
            isinstance(block, dict) and "toolResult" in block
            for message in messages for block in message.get("content", ())
        )

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any,
    ) -> AsyncIterator[dict]:
        if self.scenario == "approval":
            # The approval rail (interrupt + resume) lands in phase 2; the
            # placeholder behavior is that a listed tool call does NOT
            # interrupt the turn — it runs and the loop completes.
            if not self._called(messages):
                tool_use: dict[str, Any] = {
                    "toolUseId": "model-call", "name": "demo_tool", "input": {},
                }
                yield {"contentBlockStart": {"start": {"toolUse": tool_use}, "contentBlockIndex": 0}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"value":"x"}'}}, "contentBlockIndex": 0}}
                yield {"contentBlockStop": {"contentBlockIndex": 0}}
                yield {"messageStop": {"stopReason": "tool_use"}}
                return
            yield {"contentBlockDelta": {"delta": {"text": "Tool completed"}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        if self.scenario == "frontend":
            if not self._called(messages):
                tool_use = {"toolUseId": "fe-call-1", "name": "fe_navigate_canvas", "input": {}}
                yield {"contentBlockStart": {"start": {"toolUse": tool_use}, "contentBlockIndex": 0}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"view":"timeline-v2"}'}}, "contentBlockIndex": 0}}
                yield {"contentBlockStop": {"contentBlockIndex": 0}}
                yield {"messageStop": {"stopReason": "tool_use"}}
                return
            yield {"contentBlockDelta": {"delta": {"text": "Timeline opened"}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        yield {"contentBlockDelta": {"delta": {"text": "humans reply"}, "contentBlockIndex": 0}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class NullClient:
    """Scoped-client stub with no capabilities."""

    scope = CapabilityScope.create("strands-chat-test", set())

    async def list_capabilities(self) -> tuple[()]:
        return ()


def _chat(model: Model) -> StrandsChatAgent:
    return StrandsChatAgent(NullClient(), lambda _mid, **_kw: model, model_id="fake")
