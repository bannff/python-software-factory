"""Tests for strict LLM Gateway deterministic MCP tools."""
import asyncio

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.llm_gateway.mcp import deterministic
from factory.llm_gateway.runtime.runtime import LLMRuntime, reset_runtime


class TestListBackends:
    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    @staticmethod
    def _result(mcp: ToolCatalog):
        tool = asyncio.run(mcp.get_tool("llm_list_backends"))
        return tool.fn()

    def test_returns_successful_typed_envelope(self) -> None:
        mcp = ToolCatalog("test")
        deterministic.register(mcp, lambda: LLMRuntime())
        result = self._result(mcp)
        assert result.ok is True
        assert result.idempotency_key is None
        assert result.data is not None
        assert result.data.backends == ["bedrock", "openai", "anthropic", "ollama"]
        assert result.data.embedding_backends == ["bedrock", "openai", "ollama"]

    def test_has_strict_boundary_models(self) -> None:
        mcp = ToolCatalog("test")
        deterministic.register(mcp, lambda: LLMRuntime())
        tool = asyncio.run(mcp.get_tool("llm_list_backends"))
        assert tool.fn._mcp_category == "deterministic"
        assert tool.fn._mcp_input_model.__name__ == "EmptyInput"
        assert tool.fn._mcp_output_model.__name__ == "BackendsOutput"
