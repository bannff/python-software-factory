"""Focused strict-ingress and bounded-egress tests for LLM Gateway MCP."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.interface import SchemaMigrationError

from factory.llm_gateway.mcp import operational
from factory.llm_gateway.runtime.ports import EmbeddingResponse
from factory.llm_gateway.runtime.runtime import LLMRuntime


class TestOperationalBoundary:
    def setup_method(self) -> None:
        self.mcp = ToolCatalog("test")
        self.runtime = LLMRuntime()
        operational.register(self.mcp, lambda: self.runtime)

    def _tool(self, name: str):
        return asyncio.run(self.mcp.get_tool(name)).fn

    @pytest.mark.parametrize("kwargs", [
        {"prompt": "hello", "max_tokens": "1"},
        {"prompt": "hello", "temperature": 2.1},
        {"prompt": "hello", "extra": True},
    ])
    def test_completion_rejects_coercion_bounds_and_unknown_fields(self, kwargs: dict) -> None:
        with pytest.raises(SchemaMigrationError):
            self._tool("llm_complete")(**kwargs)

    @pytest.mark.parametrize("messages", [
        [{"role": "tool", "content": "no"}],
        [{"role": "user", "content": "ok", "extra": "no"}],
        [{"role": "user", "content": ""}],
    ])
    def test_chat_rejects_invalid_messages(self, messages: list[dict]) -> None:
        with pytest.raises(SchemaMigrationError):
            self._tool("llm_chat")(messages=messages)

    def test_embeddings_reject_anthropic_before_runtime_dispatch(self) -> None:
        with pytest.raises(SchemaMigrationError):
            self._tool("llm_embed")(texts=["hello"], backend="anthropic")

    @pytest.mark.parametrize("embeddings", [
        [[float("nan")]],
        [[0.0] * 8193],
    ])
    def test_embedding_egress_rejects_invalid_vectors(self, embeddings: list[list[float]]) -> None:
        embedder = MagicMock()
        embedder.embed.return_value = EmbeddingResponse(embeddings, "model", "provider")
        with patch.object(self.runtime, "get_embedder", return_value=embedder):
            result = self._tool("llm_embed")(texts=["hello"])
        assert result.ok is False
        assert result.error == "tool_execution_failed"

    def test_defaults_are_preserved_by_strict_input_model(self) -> None:
        provider = MagicMock()
        provider.complete.return_value = MagicMock(
            content="ok", model="model", provider="provider", usage={}, finish_reason="stop",
        )
        with patch.object(self.runtime, "get_provider", return_value=provider):
            result = self._tool("llm_complete")(prompt="hello")
        assert result.ok is True
        assert provider.complete.call_args.args[2:] == (1024, 0.7)
