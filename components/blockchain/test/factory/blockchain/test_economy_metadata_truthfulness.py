"""Truthfulness regression tests for economy-only startup metadata."""
from __future__ import annotations

import asyncio

from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server, describe_config_schema, get_capabilities, health_check


def test_metadata_advertises_supported_configuration_not_locally_provisioned_neo4j(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ADAPTER", raising=False)
    runtime = BlockchainRuntime()
    capabilities = get_capabilities()
    schema = describe_config_schema()
    readiness = health_check()
    assert capabilities["backends"] == ["mock", "neo4j"]
    assert schema["properties"]["backend"]["enum"] == ["mock", "neo4j", "mock_ledger"]
    assert readiness["provider"] == "mock_ledger"
    assert runtime.adapter_id == "mock"


def test_typed_metadata_tools_match_the_active_economy_runtime_without_live_neo4j(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ADAPTER", raising=False)
    tools = {item.name: item.fn for item in asyncio.run(create_mcp_server(BlockchainRuntime()).list_tools())}
    assert tools["blockchain_get_capabilities"]().data.backends == ["mock", "neo4j"]
    assert tools["blockchain_describe_config_schema"]().data.properties["backend"]["enum"] == ["mock", "neo4j", "mock_ledger"]
    assert tools["blockchain_health_check"]().data.provider == "mock_ledger"
