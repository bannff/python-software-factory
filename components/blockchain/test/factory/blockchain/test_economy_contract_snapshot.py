"""Discovery-level compatibility snapshot for the economy-only MCP surface."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, get_type_hints

from factory.mcp_utils.interface import ToolResult
from factory.blockchain.runtime.ledger import mock_ledger
from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server

_EXPECTED = {
    "deterministic": 13,
    "operational": 11,
    "authoring": 2,
}
_RESOURCE_URIS = {"blockchain://docs", "blockchain://templates", "blockchain://integration"}
_TEMPLATE_URIS = {"blockchain://docs/{name}", "blockchain://templates/{name}"}
_PROMPTS = {
    "blockchain_create_economy", "blockchain_transfer_tokens",
    "blockchain_post_and_claim_bounty", "blockchain_audit_chain", "blockchain_troubleshoot",
}
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT")
_ID = re.compile(r"^(tx|bounty)-[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _server():
    return create_mcp_server(BlockchainRuntime("mock"))


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str) and (_TIMESTAMP.match(value) or _ID.match(value) or _HASH.match(value)):
        return "<dynamic>"
    return value


def _tools() -> dict[str, Any]:
    return {tool.name: tool for tool in asyncio.run(_server().list_tools())}


def _disable_mock_effects(monkeypatch) -> None:
    no_op = lambda *_args, **_kwargs: None
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, no_op)
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", no_op)


def test_complete_tool_catalog_and_concrete_dto_schemas_are_frozen() -> None:
    tools = _tools()
    categories = {name: getattr(tool.fn, "_mcp_category") for name, tool in tools.items()}
    assert {category: list(categories.values()).count(category) for category in _EXPECTED} == _EXPECTED
    assert len(tools) == sum(_EXPECTED.values())
    snapshot = {}
    for name, tool in tools.items():
        output = getattr(tool.fn, "_mcp_output_model")
        assert get_type_hints(tool.fn)["return"] == ToolResult[output]
        snapshot[name] = {
            "category": categories[name],
            "input": tool.fn._mcp_input_model.model_json_schema(mode="validation"),
            "output": output.model_json_schema(),
        }
    assert _digest(snapshot) == "580e768bca550672c9ea88d82561449ad8d6c3cb13db1637cab3eaeced0eb0dd"


def test_resources_prompts_complete_view_and_representative_envelopes_are_frozen() -> None:
    server, tools = _server(), _tools()
    assert {str(item.uri) for item in asyncio.run(server.list_resources())} == _RESOURCE_URIS
    assert {item.uri_template for item in asyncio.run(server.list_resource_templates())} == _TEMPLATE_URIS
    assert {item.name for item in asyncio.run(server.list_prompts())} == _PROMPTS
    success = tools["blockchain_get_chain_info"].fn().model_dump(mode="json")
    missing = tools["blockchain_get_wallet"].fn(wallet_id="missing").model_dump(mode="json")
    negative = tools["blockchain_transfer"].fn(
        from_wallet="missing", to_wallet="wallet-treasury", amount=1,
    ).model_dump(mode="json")
    view = tools["blockchain_get_views"].fn().data.views
    assert _digest(_normalize({"success": success, "missing": missing, "negative": negative})) == "d4ac4756c50109323ddd474a36363f7e8955cafbf50ff7131d16115110f15100"
    assert _digest(view) == "7ebfe7661d3cb52d6c97dac0b142163038a931217f1f60e0acbe0d8e76dbf46f"


def test_normal_negative_envelopes_are_frozen(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS", raising=False)
    _disable_mock_effects(monkeypatch)
    tools = _tools()
    tools["blockchain_create_wallet"].fn(owner_id="snapshot-duplicate")
    monkeypatch.setattr("factory.blockchain.mcp.operational._my_wallet", lambda _runtime: "wallet-missing")
    envelopes = {
        "missing_balance": tools["blockchain_get_balance"].fn(wallet_id="missing").model_dump(mode="json"),
        "missing_block": tools["blockchain_get_block"].fn(height=999).model_dump(mode="json"),
        "duplicate_wallet": tools["blockchain_create_wallet"].fn(owner_id="snapshot-duplicate").model_dump(mode="json"),
        "reserved_wallet": tools["blockchain_create_wallet"].fn(owner_id="treasury").model_dump(mode="json"),
        "failed_mint": tools["blockchain_mint"].fn(to_wallet="missing", amount=1).model_dump(mode="json"),
        "failed_post": tools["blockchain_post_bounty"].fn(poster_wallet="missing", amount=1).model_dump(mode="json"),
        "failed_claim": tools["blockchain_claim_bounty"].fn(bounty_id="missing", claimer_wallet="wallet-treasury").model_dump(mode="json"),
        "failed_cancel": tools["blockchain_cancel_bounty"].fn(bounty_id="missing").model_dump(mode="json"),
        "failed_reconcile": tools["blockchain_reconcile"].fn(wallet_id="missing").model_dump(mode="json"),
        "auto_wallet_failure": tools["blockchain_my_wallet"].fn().model_dump(mode="json"),
        "authoring_disabled": tools["blockchain_authoring_seed_economy"].fn().model_dump(mode="json"),
    }
    assert _digest(_normalize(envelopes)) == "ca625596e7c07a547d65cd79a222a587bebdccdbd015c7dd70e42b113d88ad8a"
