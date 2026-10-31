"""Tests for LLM Gateway runtime."""

import pytest
from unittest.mock import MagicMock

from factory.llm_gateway.runtime.runtime import (
    LLMRuntime,
    get_runtime,
    reset_runtime,
)
from factory.llm_gateway.runtime.ports import LLMResponse, EmbeddingResponse


class TestLLMRuntime:
    """Tests for LLMRuntime factory."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_available_backends(self) -> None:
        """Should list available backends."""
        backends = LLMRuntime.available_backends()
        assert "bedrock" in backends
        assert "openai" in backends
        assert "anthropic" in backends
        assert "ollama" in backends

    def test_get_runtime_singleton(self) -> None:
        """Should return same runtime instance."""
        r1 = get_runtime()
        r2 = get_runtime()
        assert r1 is r2

    def test_reset_runtime(self) -> None:
        """Should reset runtime instance."""
        r1 = get_runtime()
        reset_runtime()
        r2 = get_runtime()
        assert r1 is not r2

    def test_unknown_backend_raises(self) -> None:
        """Should raise for unknown backend."""
        runtime = LLMRuntime()
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            runtime.get_provider("unknown")

    def test_unknown_embedder_backend_raises(self) -> None:
        """Should raise for unknown embedder backend."""
        runtime = LLMRuntime()
        with pytest.raises(ValueError, match="Unknown embedding backend"):
            runtime.get_embedder("unknown")

    def test_get_provider_bedrock(self) -> None:
        """Should create Bedrock provider."""
        runtime = LLMRuntime()
        # Provider is created lazily, client not initialized until first call
        provider = runtime.get_provider("bedrock")
        assert provider is not None
        assert provider._default_model == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def test_get_provider_openai(self) -> None:
        """Should create OpenAI provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("openai", api_key="test-key")
        assert provider is not None
        assert provider._api_key == "test-key"

    def test_get_provider_anthropic(self) -> None:
        """Should create Anthropic provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("anthropic", api_key="test-key")
        assert provider is not None
        assert provider._api_key == "test-key"

    def test_get_provider_ollama(self) -> None:
        """Should create Ollama provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("ollama")
        assert provider is not None
        assert provider._api_key == "ollama"
        assert provider._base_url == "http://localhost:11434/v1"
        assert provider._default_model == "llama3.2"

    def test_get_embedder_ollama(self) -> None:
        """Should create Ollama embedder."""
        runtime = LLMRuntime()
        embedder = runtime.get_embedder("ollama")
        assert embedder is not None
        assert embedder._api_key == "ollama"
        assert embedder._base_url == "http://localhost:11434/v1"
        assert embedder._default_model == "nomic-embed-text"

    def test_provider_caching(self) -> None:
        """Should cache providers with same config."""
        runtime = LLMRuntime()
        p1 = runtime.get_provider("openai", api_key="test")
        p2 = runtime.get_provider("openai", api_key="test")
        assert p1 is p2

    def test_provider_different_config(self) -> None:
        """Should create different providers for different configs."""
        runtime = LLMRuntime()
        p1 = runtime.get_provider("openai", api_key="key1")
        p2 = runtime.get_provider("openai", api_key="key2")
        assert p1 is not p2

    def test_health_check_empty(self) -> None:
        """Should return empty health when no providers active."""
        runtime = LLMRuntime()
        health = runtime.health_check()
        assert health == {}


class TestMockProvider:
    """Tests with mock providers."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_complete_mock(self) -> None:
        """Should call provider complete."""
        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Hello!",
            model="test-model",
            provider="mock",
            usage={"input_tokens": 5, "output_tokens": 2},
        )

        runtime = LLMRuntime()
        runtime._providers["mock:0"] = mock_provider

        # Access cached provider
        result = runtime._providers["mock:0"].complete("Hi")
        assert result.content == "Hello!"
        assert result.provider == "mock"

    def test_embed_mock(self) -> None:
        """Should call embedder embed."""
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3]],
            model="test-embed",
            provider="mock",
            usage={"input_tokens": 3},
        )

        runtime = LLMRuntime()
        runtime._embedders["mock:0"] = mock_embedder

        result = runtime._embedders["mock:0"].embed(["test"])
        assert len(result.embeddings) == 1
        assert result.embeddings[0] == [0.1, 0.2, 0.3]
