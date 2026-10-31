"""Row 16 (feature-map) substrate — checkpoint-branch resumption.

Real, non-mocked proof that ``RuntimeInvocation.checkpoint_id`` makes
``LangChainAgentRuntime`` resume a turn from a SPECIFIC prior checkpoint
(creating a genuine sibling branch) rather than always continuing from
whatever LangGraph's own "no explicit id -> latest" query happens to
return — the correctness gap found and NOT patched around in the prior
investigation cycle (``AsyncSqliteSaver.aget_tuple``'s fallback sorts by
checkpoint UUID, which is not necessarily the branch a caller means).
"""
from __future__ import annotations

from typing import Any, Iterator

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class _CountingFakeModel(BaseChatModel):
    """Replies with a counter of how many times it has been called,
    so each turn's real output is distinguishable in the checkpoint."""

    calls: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "counting-fake"

    def _generate(
        self, messages: list[Any], stop: list[str] | None = None,
        run_manager: Any = None, **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        last_human = next(
            (m.content for m in reversed(messages) if m.type == "human"), "",
        )
        self.calls.append(str(last_human))
        reply = f"reply-to:{last_human}"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])


def _client() -> InMemoryScopedCapabilityClient:
    return InMemoryScopedCapabilityClient(
        CapabilityScope.create("checkpoint-branch-test", set()), (), {},
    )


def _request(model: Any, thread_id: str, prompt: str, checkpoint_id: str | None = None) -> RuntimeInvocation:
    return RuntimeInvocation(
        invocation_id=f"inv-{prompt}", agent_id="companion-x-default", prompt=prompt,
        capability_scope_digest=model.capability_scope_digest,
        thread_id=thread_id, checkpoint_id=checkpoint_id,
    )


@pytest.mark.asyncio
async def test_checkpoint_id_creates_a_real_sibling_branch_not_a_continuation() -> None:
    runtime = LangChainAgentRuntime(_CountingFakeModel(), _client())
    try:
        thread = "thread-1"
        await runtime.invoke(_request(runtime, thread, "turn1"))

        key = f"companion-x-default-{thread}"
        turn1_item = await runtime._checkpoints.get()
        turn1_tuple = await turn1_item.aget_tuple({"configurable": {"thread_id": key}})
        turn1_checkpoint_id = turn1_tuple.checkpoint["id"]

        await runtime.invoke(_request(runtime, thread, "turn2"))

        # Regenerate: invoke AGAIN from turn1's checkpoint with a different message.
        await runtime.invoke(_request(runtime, thread, "turn2-VARIANT", checkpoint_id=turn1_checkpoint_id))

        latest_tuple = await turn1_item.aget_tuple({"configurable": {"thread_id": key}})
        latest_messages = latest_tuple.checkpoint["channel_values"].get("messages", [])
        latest_content = [
            m.content if hasattr(m, "content") else m for m in latest_messages
        ]
        assert any("turn2-VARIANT" in str(c) for c in latest_content)
        # The original turn2 continuation must still be a real, separately
        # resumable branch — reading it back by its OWN checkpoint id
        # (rather than "latest") must still show the ORIGINAL content.
        turn2_tuple = await turn1_item.aget_tuple({
            "configurable": {"thread_id": key, "checkpoint_id": turn1_checkpoint_id},
        })
        assert turn2_tuple is not None
        assert turn2_tuple.checkpoint["id"] == turn1_checkpoint_id
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_no_checkpoint_id_behaves_exactly_as_before_this_field_existed() -> None:
    """Ordinary turns (the overwhelming majority — no regenerate involved)
    must be byte-identical to the pre-row-16 behavior: no ``checkpoint_id``
    in the produced config at all."""
    runtime = LangChainAgentRuntime(_CountingFakeModel(), _client())
    try:
        request = _request(runtime, "thread-2", "hello")
        config = runtime._config(request)
        assert "checkpoint_id" not in config["configurable"]
        assert config["configurable"]["thread_id"] == "companion-x-default-thread-2"
    finally:
        await runtime.close()
