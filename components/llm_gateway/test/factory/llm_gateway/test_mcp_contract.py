"""Tests for strict deterministic LLM Gateway MCP contracts."""
import asyncio
from unittest.mock import MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.interface import SchemaMigrationError

from factory.llm_gateway.mcp import deterministic
from factory.llm_gateway.runtime.ports import LLMHealth
from factory.llm_gateway.runtime.runtime import LLMRuntime, reset_runtime


class TestDeterministicContracts:
    def setup_method(self) -> None:
        reset_runtime()
        self.mcp = ToolCatalog("test")
        self.runtime = LLMRuntime()
        deterministic.register(self.mcp, lambda: self.runtime)

    def teardown_method(self) -> None:
        reset_runtime()

    def _tool(self, name: str):
        return asyncio.run(self.mcp.get_tool(name)).fn

    def test_every_tool_is_typed_and_categorized(self) -> None:
        for name in ["get_capabilities", "health_check", "describe_config_schema", "llm_list_backends"]:
            tool = self._tool(name)
            assert tool._mcp_category == "deterministic"
            assert tool._mcp_input_model is not None
            assert tool._mcp_output_model is not None

    def test_capabilities_use_envelope(self) -> None:
        result = self._tool("get_capabilities")()
        assert result.ok is True
        assert result.data.name == "llm_gateway"
        assert result.data.version == "2.0.0"
        assert "embeddings" in result.data.features

    def test_empty_inputs_reject_unknown_fields(self) -> None:
        with pytest.raises(SchemaMigrationError):
            self._tool("get_capabilities")(unexpected=True)

    def test_health_omits_runtime_messages_and_details(self) -> None:
        provider = MagicMock()
        provider.health_check.return_value = LLMHealth(
            healthy=False, provider="mock", message="token=secret", details={"url": "x"},
        )
        self.runtime._providers["mock:0"] = provider
        result = self._tool("health_check")()
        status = result.data.providers["llm:mock:0"]
        assert status.healthy is False
        assert status.provider == "mock"
        assert "message" not in status.model_dump()

    def test_config_schema_exposes_only_safe_fields(self) -> None:
        result = self._tool("describe_config_schema")()
        assert result.ok is True
        assert set(result.data.properties) == {"backend", "model"}
        assert "api_key" not in result.data.model_dump_json()
        assert "base_url" not in result.data.model_dump_json()
        assert "region" not in result.data.model_dump_json()
