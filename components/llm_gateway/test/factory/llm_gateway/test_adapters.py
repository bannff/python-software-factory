"""Tests for LLM Gateway adapter selection and creation."""

import pytest
from unittest.mock import MagicMock, patch

from factory.llm_gateway.runtime.runtime import LLMRuntime, reset_runtime
from factory.llm_gateway.runtime.ports import LLMResponse, EmbeddingResponse, LLMHealth


class TestAdapterSelection:
    """Tests for adapter selection logic."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_select_bedrock_provider(self) -> None:
        """Should create Bedrock provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("bedrock")
        assert provider is not None
        # Check it's the right type by checking default model
        assert hasattr(provider, "_default_model")
        assert "anthropic.claude" in provider._default_model

    def test_select_openai_provider(self) -> None:
        """Should create OpenAI provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("openai", api_key="test-key")
        assert provider is not None
        assert provider._api_key == "test-key"

    def test_select_anthropic_provider(self) -> None:
        """Should create Anthropic provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("anthropic", api_key="test-key")
        assert provider is not None
        assert provider._api_key == "test-key"

    def test_select_ollama_provider(self) -> None:
        """Should create Ollama provider."""
        runtime = LLMRuntime()
        provider = runtime.get_provider("ollama")
        assert provider is not None
        assert provider._base_url == "http://localhost:11434/v1"

    def test_unknown_provider_raises(self) -> None:
        """Should raise for unknown provider."""
        runtime = LLMRuntime()
        with pytest.raises(ValueError, match="Unknown LLM backend"):
            runtime.get_provider("unknown")


class TestEmbedderSelection:
    """Tests for embedder selection logic."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_select_bedrock_embedder(self) -> None:
        """Should create Bedrock embedder."""
        runtime = LLMRuntime()
        embedder = runtime.get_embedder("bedrock")
        assert embedder is not None

    def test_select_openai_embedder(self) -> None:
        """Should create OpenAI embedder."""
        runtime = LLMRuntime()
        embedder = runtime.get_embedder("openai", api_key="test-key")
        assert embedder is not None

    def test_select_ollama_embedder(self) -> None:
        """Should create Ollama embedder."""
        runtime = LLMRuntime()
        embedder = runtime.get_embedder("ollama")
        assert embedder is not None
        assert embedder._base_url == "http://localhost:11434/v1"

    def test_unknown_embedder_raises(self) -> None:
        """Should raise for unknown embedder."""
        runtime = LLMRuntime()
        with pytest.raises(ValueError, match="Unknown embedding backend"):
            runtime.get_embedder("unknown")

    def test_anthropic_embedder_not_supported(self) -> None:
        """Anthropic doesn't support embeddings."""
        runtime = LLMRuntime()
        with pytest.raises(ValueError, match="Unknown embedding backend"):
            runtime.get_embedder("anthropic")


class TestAdapterCaching:
    """Tests for adapter caching behavior."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_provider_cached_same_config(self) -> None:
        """Should cache providers with same config."""
        runtime = LLMRuntime()
        p1 = runtime.get_provider("openai", api_key="test")
        p2 = runtime.get_provider("openai", api_key="test")
        assert p1 is p2

    def test_provider_not_cached_different_config(self) -> None:
        """Should create new provider for different config."""
        runtime = LLMRuntime()
        p1 = runtime.get_provider("openai", api_key="key1")
        p2 = runtime.get_provider("openai", api_key="key2")
        assert p1 is not p2

    def test_embedder_cached_same_config(self) -> None:
        """Should cache embedders with same config."""
        runtime = LLMRuntime()
        e1 = runtime.get_embedder("openai", api_key="test")
        e2 = runtime.get_embedder("openai", api_key="test")
        assert e1 is e2

    def test_embedder_not_cached_different_config(self) -> None:
        """Should create new embedder for different config."""
        runtime = LLMRuntime()
        e1 = runtime.get_embedder("openai", api_key="key1")
        e2 = runtime.get_embedder("openai", api_key="key2")
        assert e1 is not e2


class TestAdapterHealthCheck:
    """Tests for adapter health check integration."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_health_check_empty_runtime(self) -> None:
        """Should return empty health for no adapters."""
        runtime = LLMRuntime()
        health = runtime.health_check()
        assert health == {}

    def test_health_check_with_provider(self) -> None:
        """Should include provider health."""
        runtime = LLMRuntime()

        # Add mock provider
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = LLMHealth(
            healthy=True, provider="mock", latency_ms=10.0
        )
        runtime._providers["mock:0"] = mock_provider

        health = runtime.health_check()
        assert "llm:mock:0" in health
        assert health["llm:mock:0"].healthy is True

    def test_health_check_with_embedder(self) -> None:
        """Should include embedder health."""
        runtime = LLMRuntime()

        # Add mock embedder
        mock_embedder = MagicMock()
        mock_embedder.health_check.return_value = LLMHealth(
            healthy=True, provider="mock-embed", latency_ms=5.0
        )
        runtime._embedders["mock:0"] = mock_embedder

        health = runtime.health_check()
        assert "embed:mock:0" in health
        assert health["embed:mock:0"].healthy is True

    def test_health_check_unhealthy_provider(self) -> None:
        """Should report unhealthy provider."""
        runtime = LLMRuntime()

        mock_provider = MagicMock()
        mock_provider.health_check.return_value = LLMHealth(
            healthy=False, provider="mock", message="Connection failed"
        )
        runtime._providers["mock:0"] = mock_provider

        health = runtime.health_check()
        assert health["llm:mock:0"].healthy is False
        assert health["llm:mock:0"].message == "Connection failed"
