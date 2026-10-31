"""Tests for LLM Gateway MCP server integration and typed operations."""
import asyncio
from unittest.mock import MagicMock, patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.llm_gateway.mcp import operational
from factory.llm_gateway.runtime.ports import EmbeddingResponse, LLMResponse
from factory.llm_gateway.runtime.runtime import LLMRuntime, reset_runtime


class TestServerIntegration:
    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_server_registers_exact_live_tool_catalog(self) -> None:
        from factory.llm_gateway.server import get_mcp_server

        names = {tool.name for tool in asyncio.run(get_mcp_server().list_tools())}
        assert names == {
            "get_capabilities", "health_check", "describe_config_schema",
            "llm_list_backends", "llm_complete", "llm_chat", "llm_embed",
        }

    def test_resources_and_prompts_remain_native_transports(self) -> None:
        from factory.llm_gateway.server import get_mcp_server

        mcp = get_mcp_server()
        assert asyncio.run(mcp.list_resources())
        assert asyncio.run(mcp.list_resource_templates())
        assert {prompt.name for prompt in asyncio.run(mcp.list_prompts())} == {
            "configure_backend", "debug_llm", "optimize_prompts",
        }


class TestOperationalTools:
    def setup_method(self) -> None:
        reset_runtime()
        self.mcp = ToolCatalog("test")
        self.runtime = LLMRuntime()

    def teardown_method(self) -> None:
        reset_runtime()

    def _register(self) -> None:
        operational.register(self.mcp, lambda: self.runtime)

    def _tool(self, name: str):
        return asyncio.run(self.mcp.get_tool(name)).fn

    def test_completion_returns_typed_envelope(self) -> None:
        provider = MagicMock()
        provider.complete.return_value = LLMResponse("42", "test-model", "test", {"input_tokens": 5}, "stop")
        with patch.object(self.runtime, "get_provider", return_value=provider):
            self._register()
            result = self._tool("llm_complete")(prompt="What is 2+2?", backend="openai")
        assert result.ok is True
        assert result.data.content == "42"
        assert result.data.finish_reason == "stop"
        assert result.idempotency_key is None

    def test_chat_validates_and_converts_messages(self) -> None:
        provider = MagicMock()
        provider.chat.return_value = LLMResponse("Hello!", "test-model", "test")
        with patch.object(self.runtime, "get_provider", return_value=provider):
            self._register()
            result = self._tool("llm_chat")(messages=[{"role": "user", "content": "Hi"}])
        assert result.ok is True
        assert result.data.content == "Hello!"
        assert provider.chat.call_args.args[0][0].role == "user"

    def test_embedding_returns_typed_envelope(self) -> None:
        embedder = MagicMock()
        embedder.embed.return_value = EmbeddingResponse([[0.1, 0.2]], "test-embed", "test", {"input_tokens": 5})
        with patch.object(self.runtime, "get_embedder", return_value=embedder):
            self._register()
            result = self._tool("llm_embed")(texts=["Hello world"], backend="openai")
        assert result.ok is True
        assert result.data.embeddings == [[0.1, 0.2]]

    def test_provider_exception_returns_safe_failure_envelope(self) -> None:
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("api_key=secret endpoint=https://private")
        with patch.object(self.runtime, "get_provider", return_value=provider):
            self._register()
            result = self._tool("llm_complete")(prompt="hello")
        assert result.ok is False
        assert result.data is None
        assert result.error == "tool_execution_failed"

    def test_all_operational_tools_have_contract_metadata(self) -> None:
        self._register()
        for name in ["llm_complete", "llm_chat", "llm_embed"]:
            tool = self._tool(name)
            assert tool._mcp_category == "operational"
            assert tool._mcp_input_model is not None
            assert tool._mcp_output_model is not None
