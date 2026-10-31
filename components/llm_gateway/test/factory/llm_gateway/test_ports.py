"""Tests for LLM Gateway ports (data classes)."""

from factory.llm_gateway.runtime.ports import (
    LLMHealth,
    LLMMessage,
    LLMResponse,
    EmbeddingResponse,
)


class TestLLMHealth:
    """Tests for LLMHealth dataclass."""

    def test_healthy_status(self) -> None:
        """Should create healthy status."""
        health = LLMHealth(healthy=True, provider="test", latency_ms=10.5)
        assert health.healthy is True
        assert health.provider == "test"
        assert health.latency_ms == 10.5
        assert health.message == ""

    def test_unhealthy_status(self) -> None:
        """Should create unhealthy status with message."""
        health = LLMHealth(
            healthy=False,
            provider="test",
            latency_ms=100.0,
            message="Connection failed",
        )
        assert health.healthy is False
        assert health.message == "Connection failed"

    def test_details_default(self) -> None:
        """Should have empty details by default."""
        health = LLMHealth(healthy=True, provider="test")
        assert health.details == {}


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""

    def test_user_message(self) -> None:
        """Should create user message."""
        msg = LLMMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_system_message(self) -> None:
        """Should create system message."""
        msg = LLMMessage(role="system", content="You are helpful.")
        assert msg.role == "system"
        assert msg.content == "You are helpful."

    def test_assistant_message(self) -> None:
        """Should create assistant message."""
        msg = LLMMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_response(self) -> None:
        """Should create basic response."""
        response = LLMResponse(
            content="Hello!",
            model="gpt-4",
            provider="openai",
        )
        assert response.content == "Hello!"
        assert response.model == "gpt-4"
        assert response.provider == "openai"
        assert response.finish_reason == "stop"

    def test_response_with_usage(self) -> None:
        """Should create response with usage stats."""
        response = LLMResponse(
            content="Test",
            model="claude-3",
            provider="anthropic",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5

    def test_response_with_metadata(self) -> None:
        """Should create response with metadata."""
        response = LLMResponse(
            content="Test",
            model="test",
            provider="test",
            metadata={"request_id": "abc123"},
        )
        assert response.metadata["request_id"] == "abc123"


class TestEmbeddingResponse:
    """Tests for EmbeddingResponse dataclass."""

    def test_single_embedding(self) -> None:
        """Should create single embedding response."""
        response = EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3]],
            model="text-embedding-3-small",
            provider="openai",
        )
        assert len(response.embeddings) == 1
        assert response.embeddings[0] == [0.1, 0.2, 0.3]

    def test_multiple_embeddings(self) -> None:
        """Should create multiple embedding response."""
        response = EmbeddingResponse(
            embeddings=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            model="titan-embed",
            provider="bedrock",
        )
        assert len(response.embeddings) == 3

    def test_embedding_with_usage(self) -> None:
        """Should create embedding with usage stats."""
        response = EmbeddingResponse(
            embeddings=[[0.1]],
            model="test",
            provider="test",
            usage={"input_tokens": 100},
        )
        assert response.usage["input_tokens"] == 100
