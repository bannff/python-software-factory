"""Focused fake-model tests for the optional LangChain chat runtime."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from factory.agent.registry.defaults import AGENTS_TYPED
from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent
from factory.agent.runtime.adapters.langchain_runtime import LangChainAgentRuntime
from factory.agent.runtime.chat_port import ChatAgentPort
from factory.agent.runtime.registry_contracts import AgentConfig
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.agent.runtime.runtime_ports import AgentRuntimePort
from factory.mcp_utils.runtime.scoped_capability_client import (
    CapabilityAccessError, InMemoryScopedCapabilityClient,
)
from factory.mcp_utils.runtime.scoped_capabilities import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


class RecordingFakeModel(BaseChatModel):
    """Runnable fake that records the exact state LangGraph supplies."""

    seen: list[list[Any]] = Field(default_factory=list)
    use_tool: bool = False

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> RecordingFakeModel:
        del tools, kwargs
        return self

    def _reply(self, messages: list[Any]) -> AIMessage:
        self.seen.append(list(messages))
        if self.use_tool and not any(isinstance(item, ToolMessage) for item in messages):
            return AIMessage(content="", tool_calls=[{
                "name": "echo", "args": {"value": "scoped"},
                "id": "call-1", "type": "tool_call",
            }])
        humans = sum(item.type == "human" for item in messages)
        return AIMessage(content=f"humans:{humans}")

    def _generate(
        self, messages: list[Any], stop: list[str] | None = None,
        run_manager: Any = None, **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
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
                    "name": call["name"],
                    "args": '{"value":"scoped"}',
                    "id": call["id"],
                    "index": 0,
                    "type": "tool_call_chunk",
                }],
            ))
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=reply.content))


async def _echo(request: Any) -> CapabilityResult:
    return CapabilityResult(content=({"type": "text", "text": request.arguments["value"]},))


def _client() -> InMemoryScopedCapabilityClient:
    return InMemoryScopedCapabilityClient(
        CapabilityScope.create("chat-test", {"echo"}),
        (CapabilityDescriptor("echo", "Echo one value", {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        }),),
        {"echo": _echo},
    )


def _adapter(model: RecordingFakeModel) -> tuple[LangChainAgentRuntime, LangChainChatAgent]:
    runtime = LangChainAgentRuntime(model, _client())
    return runtime, LangChainChatAgent(runtime)


@pytest.mark.asyncio
async def test_preserves_thread_and_persona_identity() -> None:
    runtime, chat = _adapter(RecordingFakeModel())
    alternate = AgentConfig(id="langchain-test", name="LC", model="fake", system_prompt="alternate")
    AGENTS_TYPED.append(alternate)
    try:
        assert (await chat.invoke("thread", "one")).output == "humans:1"
        assert (await chat.invoke("thread", "two")).output == "humans:2"
        assert (await chat.invoke("thread", "one", agent_id=alternate.id)).output == "humans:1"
    finally:
        AGENTS_TYPED.remove(alternate)
        await runtime.close()


@pytest.mark.asyncio
async def test_invokes_only_scoped_capability_with_correlation() -> None:
    client = _client()
    runtime = LangChainAgentRuntime(RecordingFakeModel(use_tool=True), client)
    chat = LangChainChatAgent(runtime)
    result = await chat.invoke("tool-thread", "use echo")
    assert result.output == "humans:1"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call.name == "echo" and call.arguments == {"value": "scoped"}
    assert call.correlation["agent_id"] == "companion-x-default"
    assert call.correlation["thread_id"] == "tool-thread"
    assert call.idempotency_key.startswith("langchain:")
    await runtime.close()


@pytest.mark.asyncio
async def test_stream_emits_normalized_chat_contract() -> None:
    runtime, chat = _adapter(RecordingFakeModel())
    events = [event async for event in chat.stream("stream-thread", "hello")]
    assert [event.type for event in events] == ["text_delta", "done"]
    assert events[0].content == "humans:1"
    assert events[0].message_id
    await runtime.close()


@pytest.mark.asyncio
async def test_stream_normalizes_tool_calls_and_results() -> None:
    runtime, chat = _adapter(RecordingFakeModel(use_tool=True))
    events = [event async for event in chat.stream("stream-tool", "echo")]
    assert [event.type for event in events] == [
        "tool_call_delta", "tool_result", "text_delta", "done",
    ]
    assert events[0].tool_call_id == events[1].tool_call_id == "call-1"
    await runtime.close()


@pytest.mark.asyncio
async def test_stream_accepts_an_explicit_memory_mode(monkeypatch) -> None:
    """Row 3 (feature-map): stream() (the real AG-UI/CopilotKit entry
    point via get_chat_agent_stream) must accept memory_mode and thread
    it into the built request without changing the stream's own shape."""
    runtime, chat = _adapter(RecordingFakeModel())
    seen: list[str] = []
    original = chat._request

    def _capture(*args, **kwargs):
        request = original(*args, **kwargs)
        seen.append(request.memory_mode)
        return request

    monkeypatch.setattr(chat, "_request", _capture)
    events = [event async for event in chat.stream(
        "stream-mode", "hello", memory_mode="incognito",
    )]
    assert [event.type for event in events] == ["text_delta", "done"]
    assert seen == ["incognito"]
    await runtime.close()


@pytest.mark.asyncio
async def test_close_resets_thread_and_aclose_is_idempotent() -> None:
    client = _client()
    runtime = LangChainAgentRuntime(RecordingFakeModel(), client)
    chat = LangChainChatAgent(runtime)
    await chat.invoke("reset-thread", "one")
    assert (await chat.invoke("reset-thread", "two")).output == "humans:2"
    chat.close("reset-thread")
    assert (await chat.invoke("reset-thread", "fresh")).output == "humans:1"
    await chat.aclose()
    await chat.aclose()
    with pytest.raises(CapabilityAccessError, match="closed"):
        await client.list_capabilities()


def test_existing_runtime_ports_accept_langchain_adapters() -> None:
    runtime, chat = _adapter(RecordingFakeModel())
    assert isinstance(runtime, AgentRuntimePort)
    assert isinstance(chat, ChatAgentPort)


@pytest.mark.asyncio
async def test_durable_checkpoint_survives_runtime_restart(tmp_path) -> None:
    checkpoint_path = tmp_path / "agent-checkpoints.db"
    first_runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    first_chat = LangChainChatAgent(first_runtime)
    assert (await first_chat.invoke("durable-thread", "one")).output == "humans:1"
    first_history = await first_chat.history("companion-x-default", "durable-thread")
    assert [item["role"] for item in first_history] == ["user", "assistant"]
    assert [item["content"] for item in first_history] == ["one", "humans:1"]
    assert all(item["id"] for item in first_history)
    await first_runtime.close()

    second_runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    second_chat = LangChainChatAgent(second_runtime)
    assert (await second_chat.invoke("durable-thread", "two")).output == "humans:2"
    await second_runtime.close()

    import sqlite3
    with sqlite3.connect(checkpoint_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal"


@pytest.mark.asyncio
async def test_fork_thread_copies_the_complete_transcript(tmp_path) -> None:
    """Row 3 (feature-map, upstream Fork contract): a forked thread starts
    with the EXACT same transcript as its source, then evolves
    independently -- a later turn on either thread must not leak into
    the other."""
    checkpoint_path = tmp_path / "fork-checkpoints.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    assert (await chat.invoke("source-thread", "one")).output == "humans:1"
    assert (await chat.invoke("source-thread", "two")).output == "humans:2"

    copied = await runtime.fork_thread(
        "companion-x-default", "source-thread", "forked-thread",
    )
    assert copied is True

    source_history = await chat.history("companion-x-default", "source-thread")
    forked_history = await chat.history("companion-x-default", "forked-thread")
    assert [item["content"] for item in forked_history] == \
        [item["content"] for item in source_history]

    # Independent evolution: a new turn on the fork must not appear on
    # the source, and vice versa.
    assert (await chat.invoke("forked-thread", "three")).output == "humans:3"
    source_after = await chat.history("companion-x-default", "source-thread")
    forked_after = await chat.history("companion-x-default", "forked-thread")
    assert len(source_after) == len(source_history)
    assert len(forked_after) == len(source_history) + 2
    await runtime.close()


@pytest.mark.asyncio
async def test_fork_thread_is_false_for_an_empty_source(tmp_path) -> None:
    checkpoint_path = tmp_path / "fork-empty.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    assert await runtime.fork_thread(
        "companion-x-default", "never-started", "empty-fork",
    ) is False
    await runtime.close()


@pytest.mark.asyncio
async def test_checkpoint_before_message_finds_the_resume_point_for_regenerate(tmp_path) -> None:
    """Row 16 (feature-map) — the real chain-walk proof, at the runtime
    level this time (complementing the lower-level
    ``test_checkpoint_branch_resumption.py`` proof against the raw
    checkpointer): given the id of the human message whose reply should
    be regenerated, the returned checkpoint id must be the exact resume
    point that reproduces everything up to (but not including) that
    reply, and re-invoking from it must create a genuine sibling branch."""
    checkpoint_path = tmp_path / "regen-checkpoints.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    await chat.invoke("regen-thread", "one")
    await chat.invoke("regen-thread", "two")

    history_before = await chat.history("companion-x-default", "regen-thread")
    turn2_human_id = next(
        item["id"] for item in history_before if item["role"] == "user" and item["content"] == "two"
    )

    resume_point = await runtime.checkpoint_before_message(
        "companion-x-default", "regen-thread", turn2_human_id,
    )
    assert resume_point is not None

    from factory.agent.runtime.runtime_contracts import RuntimeInvocation
    request = RuntimeInvocation(
        invocation_id="regen-inv", agent_id="companion-x-default",
        prompt="two-variant", capability_scope_digest=runtime.capability_scope_digest,
        thread_id="regen-thread", checkpoint_id=resume_point,
    )
    await runtime.invoke(request)

    history_after = await chat.history("companion-x-default", "regen-thread")
    contents = [item["content"] for item in history_after if item["role"] == "user"]
    assert contents == ["one", "two", "two-variant"]
    await runtime.close()


@pytest.mark.asyncio
async def test_checkpoint_before_message_returns_none_for_an_unknown_message_id(tmp_path) -> None:
    checkpoint_path = tmp_path / "regen-unknown.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    await chat.invoke("regen-thread-2", "one")
    resume_point = await runtime.checkpoint_before_message(
        "companion-x-default", "regen-thread-2", "nonexistent-message-id",
    )
    assert resume_point is None
    await runtime.close()


@pytest.mark.asyncio
async def test_invoke_with_a_checkpoint_id_surfaces_the_resulting_branch_id(tmp_path) -> None:
    """Row 16 — ``RuntimeResult.metadata['checkpoint_id']`` must carry the
    NEW checkpoint the regenerate call just wrote (not the input resume
    point), so the caller can persist it as the thread's new "current"
    branch. Ordinary turns (no ``checkpoint_id`` on the request) must NOT
    pay for the extra ``aget_state`` round trip or carry this key at all."""
    checkpoint_path = tmp_path / "regen-metadata.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    await chat.invoke("regen-thread-3", "one")
    await chat.invoke("regen-thread-3", "two")

    history_before = await chat.history("companion-x-default", "regen-thread-3")
    turn2_human_id = next(
        item["id"] for item in history_before if item["role"] == "user" and item["content"] == "two"
    )
    resume_point = await runtime.checkpoint_before_message(
        "companion-x-default", "regen-thread-3", turn2_human_id,
    )

    from factory.agent.runtime.runtime_contracts import RuntimeInvocation
    ordinary = RuntimeInvocation(
        invocation_id="ordinary-inv", agent_id="companion-x-default",
        prompt="three", capability_scope_digest=runtime.capability_scope_digest,
        thread_id="regen-thread-3",
    )
    ordinary_result = await runtime.invoke(ordinary)
    assert "checkpoint_id" not in ordinary_result.metadata

    regen = RuntimeInvocation(
        invocation_id="regen-inv-2", agent_id="companion-x-default",
        prompt="two-variant", capability_scope_digest=runtime.capability_scope_digest,
        thread_id="regen-thread-3", checkpoint_id=resume_point,
    )
    regen_result = await runtime.invoke(regen)
    assert regen_result.metadata["checkpoint_id"]
    assert regen_result.metadata["checkpoint_id"] != resume_point
    await runtime.close()


@pytest.mark.asyncio
async def test_regenerate_turn_creates_a_sibling_branch_and_returns_its_id(tmp_path) -> None:
    """Row 16 (feature-map) — the full composed operation at the
    ``LangChainChatAgent`` level: given the id of a human message, produce
    a genuine sibling branch with a new reply and return the checkpoint
    id to persist, leaving the ORIGINAL reply independently resumable."""
    checkpoint_path = tmp_path / "regen-composed.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    await chat.invoke("regen-thread-4", "one")
    await chat.invoke("regen-thread-4", "two")

    history_before = await chat.history("companion-x-default", "regen-thread-4")
    turn2_human_id = next(
        item["id"] for item in history_before if item["role"] == "user" and item["content"] == "two"
    )

    new_branch_id = await chat.regenerate_turn(
        "companion-x-default", "regen-thread-4", turn2_human_id, "two-variant",
    )
    assert new_branch_id is not None

    history_after = await chat.history("companion-x-default", "regen-thread-4")
    user_contents = [item["content"] for item in history_after if item["role"] == "user"]
    assert user_contents == ["one", "two", "two-variant"]
    await runtime.close()


@pytest.mark.asyncio
async def test_regenerate_turn_returns_none_for_an_unknown_message_id(tmp_path) -> None:
    checkpoint_path = tmp_path / "regen-composed-unknown.db"
    runtime = LangChainAgentRuntime(
        RecordingFakeModel(), _client(), checkpoint_path=checkpoint_path,
    )
    chat = LangChainChatAgent(runtime)
    await chat.invoke("regen-thread-5", "one")
    result = await chat.regenerate_turn(
        "companion-x-default", "regen-thread-5", "nonexistent-message-id", "one-variant",
    )
    assert result is None
    await runtime.close()


def test_chat_request_carries_verified_session_identity() -> None:
    class Runtime:
        capability_scope_digest = "scope"

    chat = LangChainChatAgent(Runtime())
    request = chat._request(
        "thread-a", "hello", None,
        tenant_id="tenant-a", owner_id="owner-a",
    )
    assert request.tenant_id == "tenant-a"
    assert request.owner_id == "owner-a"
    assert request.model_id == ""
    assert request.memory_mode == ""


def test_chat_request_carries_an_explicit_memory_mode_choice() -> None:
    """Row 3 (feature-map): the AG-UI boundary's resolved choice (owner
    default or an explicit per-chat override) must reach the built
    RuntimeInvocation unchanged, exactly like tenant_id/owner_id."""
    class Runtime:
        capability_scope_digest = "scope"

    chat = LangChainChatAgent(Runtime())
    request = chat._request(
        "thread-b", "hello", None,
        tenant_id="tenant-a", owner_id="owner-a", memory_mode="temporary",
    )
    assert request.memory_mode == "temporary"


@pytest.mark.asyncio
async def test_compiled_agent_consumes_steer_at_model_boundary() -> None:
    from factory.agent.runtime.adapters.langchain_steering import SteerDelivery

    delivery = SteerDelivery(
        tenant_id="tenant-1", owner_id="owner-1", session_id="session-1",
        delivery_id="delivery-1", send_id="send-1", content="new constraint",
        revision=1,
    )

    class Port:
        consumed = False
        requeued: list[str] = []

        def ensure(self, request):
            return "session-1"

        def written(self, request):
            return () if self.consumed else (delivery,)

        def consume(self, item):
            assert item == delivery
            self.consumed = True
            return True

        def requeue_written(self, request):
            values = self.written(request)
            self.requeued.extend(item.delivery_id for item in values)
            return tuple(self.requeued)

    port = Port()
    runtime = LangChainAgentRuntime(RecordingFakeModel(), _client(), steering=port)
    request = RuntimeInvocation(
        invocation_id="steered-run", agent_id="companion-x-default", prompt="start",
        capability_scope_digest=runtime.capability_scope_digest,
        thread_id="thread-1", tenant_id="tenant-1", owner_id="owner-1",
    )
    result = await runtime.invoke(request)
    assert result.output == "humans:2"
    assert port.consumed is True
    assert port.requeued == []
    await runtime.close()
