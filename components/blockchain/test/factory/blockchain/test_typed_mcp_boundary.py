"""Fresh-server strict boundary tests for Blockchain's complete MCP surface."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest
from pydantic import BaseModel, ValidationError

from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult


EXPECTED = {
    "deterministic": {"blockchain_get_capabilities", "blockchain_health_check", "blockchain_describe_config_schema", "blockchain_get_chain_info", "blockchain_get_balance", "blockchain_get_wallet", "blockchain_list_transactions", "blockchain_get_block", "blockchain_verify_chain", "blockchain_get_dashboard_summary", "blockchain_get_activity", "blockchain_get_entity_graph_context", "blockchain_get_views"},
    "operational": {"blockchain_my_wallet", "blockchain_create_wallet", "blockchain_transfer", "blockchain_mint", "blockchain_reward_escrow", "blockchain_reward_release", "blockchain_post_bounty", "blockchain_claim_bounty", "blockchain_cancel_bounty", "blockchain_list_bounties", "blockchain_reconcile"},
    "authoring": {"blockchain_authoring_get_status", "blockchain_authoring_seed_economy"},
}


def _tools():
    server = create_mcp_server(BlockchainRuntime("mock"))
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_fresh_server_has_exact_typed_26_tool_catalog() -> None:
    tools = _tools()
    expected = set().union(*EXPECTED.values())
    actual = {name for name in tools if name.startswith("blockchain_")}
    assert actual == expected
    assert sum(map(len, EXPECTED.values())) == 26
    for category, names in EXPECTED.items():
        for name in names:
            fn = tools[name].fn
            assert getattr(fn, "_mcp_category") == category
            input_model = getattr(fn, "_mcp_input_model")
            output_model = getattr(fn, "_mcp_output_model")
            assert issubclass(input_model, BaseModel)
            assert issubclass(output_model, BaseModel)
            assert input_model.model_config["extra"] == "forbid"
            assert get_type_hints(fn)["return"] == ToolResult[output_model]


def test_typed_defaults_reject_unknown_kwargs_and_normal_miss_is_success() -> None:
    tools = _tools()
    with pytest.raises(Exception):
        tools["blockchain_get_wallet"].fn(wallet_id="missing", unknown=True)
    result = tools["blockchain_get_wallet"].fn(wallet_id="missing")
    assert result.ok and result.data is not None
    assert result.data.found is False and result.data.error == "not_found"
    listed = tools["blockchain_list_transactions"].fn()
    assert listed.ok and listed.data.count >= 1


def test_views_and_disabled_authoring_are_successful_typed_data(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS", raising=False)
    tools = _tools()
    views = tools["blockchain_get_views"].fn()
    disabled = tools["blockchain_authoring_seed_economy"].fn()
    assert views.ok and views.data.views[0]["id"] == "blockchain-economy"
    assert disabled.ok and disabled.data.ok is False
    assert disabled.data.error == "authoring_disabled"
