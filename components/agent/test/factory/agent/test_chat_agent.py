"""Tests for MemoryChatAgent and the get_chat_agent singleton.

Covers invoke/close behavior, multi-thread independence, and singleton lifecycle.
"""

from __future__ import annotations

import pytest

from factory.agent.runtime.adapters.memory import MemoryChatAgent
from factory.agent.runtime.chat import get_chat_agent, reset_chat_agent
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope


@pytest.fixture(autouse=True)
def native_runtime_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the native scoped-capability seam for production-default chat tests."""
    from factory.agent.runtime import adapters
    from factory.agent.runtime.adapters import langchain_model

    monkeypatch.setattr(
        adapters, "_scoped_client",
        lambda: InMemoryScopedCapabilityClient(
            CapabilityScope.create("chat-test", set()), (), {},
        ),
    )
    monkeypatch.setattr(langchain_model, "build_langchain_chat_model", lambda _: object())


class TestMemoryChatAgent:
    """Unit tests for MemoryChatAgent."""

    @pytest.mark.asyncio
    async def test_invoke_returns_completed_result(self) -> None:
        """Basic invoke returns AgentResult with status completed."""
        agent = MemoryChatAgent()
        result = await agent.invoke("t1", "hello")
        assert result.status == "completed"
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_invoke_tracks_turn_count(self) -> None:
        """Each invoke increments the turn counter for that thread."""
        agent = MemoryChatAgent()
        r1 = await agent.invoke("t1", "first")
        r2 = await agent.invoke("t1", "second")
        assert r1.metadata["turn"] == 1
        assert r2.metadata["turn"] == 2

    @pytest.mark.asyncio
    async def test_invoke_includes_thread_id_in_metadata(self) -> None:
        """Metadata contains the thread_id."""
        agent = MemoryChatAgent()
        result = await agent.invoke("my-thread", "hi")
        assert result.metadata["thread_id"] == "my-thread"

    @pytest.mark.asyncio
    async def test_invoke_truncates_long_message(self) -> None:
        """Output includes at most 50 chars of the original message."""
        agent = MemoryChatAgent()
        long_msg = "x" * 200
        result = await agent.invoke("t1", long_msg)
        # The output should contain the truncated message (50 chars)
        assert "x" * 50 in result.output
        assert "x" * 51 not in result.output

    @pytest.mark.asyncio
    async def test_close_clears_thread_history(self) -> None:
        """After close, the thread's turn counter resets."""
        agent = MemoryChatAgent()
        await agent.invoke("t1", "msg1")
        await agent.invoke("t1", "msg2")
        agent.close("t1")
        # Next invoke should start at turn 1 again
        result = await agent.invoke("t1", "msg3")
        assert result.metadata["turn"] == 1

    def test_close_nonexistent_thread_is_noop(self) -> None:
        """Closing a thread that doesn't exist doesn't raise."""
        agent = MemoryChatAgent()
        agent.close("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_threads_independent(self) -> None:
        """Different thread_ids maintain independent histories."""
        agent = MemoryChatAgent()
        await agent.invoke("a", "msg1")
        await agent.invoke("a", "msg2")
        await agent.invoke("b", "msg1")

        ra = await agent.invoke("a", "msg3")
        rb = await agent.invoke("b", "msg2")

        assert ra.metadata["turn"] == 3
        assert rb.metadata["turn"] == 2

    @pytest.mark.asyncio
    async def test_close_one_thread_does_not_affect_other(self) -> None:
        """Closing thread A doesn't reset thread B."""
        agent = MemoryChatAgent()
        await agent.invoke("a", "msg")
        await agent.invoke("b", "msg")
        agent.close("a")

        rb = await agent.invoke("b", "msg2")
        assert rb.metadata["turn"] == 2

    @pytest.mark.asyncio
    async def test_set_default_response(self) -> None:
        """Custom default response is used in output."""
        agent = MemoryChatAgent()
        agent.set_default_response("custom reply")
        result = await agent.invoke("t1", "hi")
        assert "custom reply" in result.output

    @pytest.mark.asyncio
    async def test_invoke_with_tools_param(self) -> None:
        """Tools parameter is accepted without error."""
        agent = MemoryChatAgent()
        result = await agent.invoke("t1", "hi", tools=["tool_a", "tool_b"])
        assert result.status == "completed"


class TestGetChatAgent:
    """Tests for the get_chat_agent / reset_chat_agent singleton."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_chat_agent()

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_chat_agent()

    def test_returns_same_instance(self) -> None:
        """Repeated calls return the same object."""
        a = get_chat_agent()
        b = get_chat_agent()
        assert a is b

    def test_reset_clears_singleton(self) -> None:
        """After reset, a new instance is created."""
        a = get_chat_agent()
        reset_chat_agent()
        b = get_chat_agent()
        assert a is not b

    def test_returns_chat_agent_port(self) -> None:
        """Singleton returns an object satisfying ChatAgentPort."""
        agent = get_chat_agent()
        # Must have invoke and close methods regardless of backend
        assert callable(getattr(agent, "invoke", None))
        assert callable(getattr(agent, "close", None))


def test_get_chat_agent_stream_forwards_memory_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Row 3 (feature-map): the real ``factory.agent.interface`` boundary
    the api base imports must forward an explicit memory_mode through to
    the underlying singleton's stream() call, unchanged."""
    from factory.agent.runtime import chat as chat_module

    captured: dict = {}

    class FakeAgent:
        def stream(self, thread_id, message, **kwargs):
            captured.update(kwargs)
            captured["thread_id"] = thread_id
            captured["message"] = message
            return iter(())

    monkeypatch.setattr(chat_module, "get_chat_agent", lambda: FakeAgent())
    chat_module.get_chat_agent_stream(
        "thread-x", "hi", memory_mode="temporary",
        tenant_id="tenant-a", owner_id="owner-a",
    )
    assert captured["memory_mode"] == "temporary"
    assert captured["tenant_id"] == "tenant-a" and captured["owner_id"] == "owner-a"


def test_get_chat_agent_stream_defaults_memory_mode_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """No explicit per-chat choice must forward as ``None``, never an
    invented default -- the session-binding seam owns that resolution."""
    from factory.agent.runtime import chat as chat_module

    captured: dict = {}

    class FakeAgent:
        def stream(self, thread_id, message, **kwargs):
            captured.update(kwargs)
            return iter(())

    monkeypatch.setattr(chat_module, "get_chat_agent", lambda: FakeAgent())
    chat_module.get_chat_agent_stream("thread-x", "hi")
    assert captured["memory_mode"] is None


@pytest.mark.asyncio
async def test_close_chat_agent_releases_singleton() -> None:
    from factory.agent.runtime import chat as chat_module

    class Closable:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    value = Closable()
    chat_module._chat_agent = value
    await chat_module.close_chat_agent()
    assert value.closed is True
    assert chat_module._chat_agent is None
