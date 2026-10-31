"""Normalized economy behavior transcript through the public MCP functions."""
from __future__ import annotations

import asyncio
import re

from factory.blockchain.runtime.ledger import mock_ledger
from factory.blockchain.runtime.runtime import BlockchainRuntime
from factory.blockchain.server import create_mcp_server

_DYNAMIC = re.compile(r"^(tx|bounty)-[0-9a-f]{12}$")


def _tools(runtime: BlockchainRuntime):
    server = create_mcp_server(runtime)
    return {tool.name: tool.fn for tool in asyncio.run(server.list_tools())}


def _id(value: str | None) -> str | None:
    return "<dynamic>" if value and _DYNAMIC.match(value) else value


def test_mock_economy_transcript_including_normal_negatives_and_auto_wallet(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS", raising=False)
    no_op = lambda *_args, **_kwargs: None
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, no_op)
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", no_op)
    runtime = BlockchainRuntime("mock")
    tools = _tools(runtime)
    chain = tools["blockchain_get_chain_info"]().data
    alice = tools["blockchain_create_wallet"](owner_id="alice", initial_balance=100).data
    bob = tools["blockchain_create_wallet"](owner_id="bob").data
    duplicate = tools["blockchain_create_wallet"](owner_id="alice").data
    missing = tools["blockchain_get_wallet"](wallet_id="missing").data
    transfer = tools["blockchain_transfer"](from_wallet=alice.wallet_id, to_wallet=bob.wallet_id, amount=25).data
    rejected = tools["blockchain_transfer"](from_wallet=alice.wallet_id, to_wallet=bob.wallet_id, amount=100).data
    minted = tools["blockchain_mint"](to_wallet=bob.wallet_id, amount=5).data
    bounty = tools["blockchain_post_bounty"](poster_wallet=alice.wallet_id, amount=20, description="review").data
    claimed = tools["blockchain_claim_bounty"](bounty_id=bounty.bounty_id, claimer_wallet=bob.wallet_id).data
    cancel = tools["blockchain_post_bounty"](poster_wallet=alice.wallet_id, amount=10).data
    cancelled = tools["blockchain_cancel_bounty"](bounty_id=cancel.bounty_id).data
    monkeypatch.setattr("factory.blockchain.runtime.auto_wallet._resolve_principal", lambda: "kiro-agent")
    automatic = tools["blockchain_my_wallet"]().data
    transcript = {
        "genesis": (chain.height, chain.wallet_count, chain.tx_count),
        "wallets": (alice.wallet_id, bob.wallet_id, duplicate.found, missing.error),
        "transfers": (transfer.success, rejected.success, minted.tx_type),
        "bounties": (bounty.status, claimed.tx_type, cancelled.tx_type),
        "integrity": (runtime.get_ledger().verify_chain()["valid"], runtime.get_ledger().reconcile(alice.wallet_id)["drift"]),
        "automatic": automatic.wallet_id,
        "authoring": tools["blockchain_authoring_seed_economy"]().data.error,
    }
    assert transcript == {
        "genesis": (1, 1, 1), "wallets": ("wallet-alice", "wallet-bob", False, "not_found"),
        "transfers": (True, False, "mint"), "bounties": ("open", "bounty_release", "bounty_release"),
        "integrity": (True, 0.0), "automatic": "wallet-kiro-agent", "authoring": "authoring_disabled",
    }
    assert all(_id(value) == "<dynamic>" for value in (transfer.tx_id, minted.tx_id, bounty.bounty_id, claimed.tx_id, cancelled.tx_id))


def test_authoring_enabled_transcript_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS", "1")
    seeded = _tools(BlockchainRuntime("mock"))["blockchain_authoring_seed_economy"](agent_count=2, initial_balance=10).data
    assert (seeded.ok, seeded.wallets_created, [wallet.wallet_id for wallet in seeded.wallets]) == (
        True, 2, ["wallet-agent-000", "wallet-agent-001"],
    )
