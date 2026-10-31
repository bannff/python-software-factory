"""Public runtime and metadata remain economy-only and selector-free."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server


def _tools():
    server = create_mcp_server(BlockchainRuntime("mock"))
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_runtime_exposes_only_no_argument_economy_ledger_accessor() -> None:
    assert list(inspect.signature(BlockchainRuntime.get_ledger).parameters) == ["self"]
    assert not hasattr(BlockchainRuntime, "execute")


def test_economy_tools_expose_no_profile_or_backend_selectors() -> None:
    blocked = {"profile", "ledger_type", "backend"}
    for tool in _tools().values():
        schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
        assert not blocked.intersection(schema.get("properties", {}))
        assert not blocked.intersection(inspect.signature(tool.fn).parameters)


def test_no_request_context_or_generic_profile_route_reaches_runtime_construction() -> None:
    runtime_source = inspect.getsource(BlockchainRuntime)
    server_source = Path("components/blockchain/src/factory/blockchain/server.py").read_text()
    assert "def get_ledger(self, " not in runtime_source
    assert "def execute" not in runtime_source
    assert "request" not in runtime_source + server_source
    assert "context" not in runtime_source + server_source
    assert "blockchain_execute" not in {tool.name for tool in _tools().values()}


def test_metadata_reports_only_economy_adapter_facts() -> None:
    tools = _tools()
    capabilities = tools["blockchain_get_capabilities"].fn().data
    schema = tools["blockchain_describe_config_schema"].fn().data
    health = tools["blockchain_health_check"].fn().data
    assert capabilities.backends == ["mock", "neo4j"]
    assert schema.properties["backend"]["enum"] == ["mock", "neo4j", "mock_ledger"]
    assert health.provider == "mock_ledger"
    assert "profile" not in schema.properties
