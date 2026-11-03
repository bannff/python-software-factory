from __future__ import annotations

import asyncio

from factory.blockchain.server import create_tool_catalog


def _tools():
    return {t.name: t.fn for t in asyncio.run(create_tool_catalog().list_tools())}


def _funded(tools, owner: str, amount: float = 20):
    tools["blockchain_create_wallet"](owner_id=owner)
    tools["blockchain_mint"](to_wallet=f"wallet-{owner}", amount=amount)
    return f"wallet-{owner}"


def test_bounty_refusals_are_typed_codes() -> None:
    tools = _tools()
    poster, claimer = _funded(tools, "bp"), _funded(tools, "bc", 0)
    assert tools["blockchain_post_bounty"](poster_wallet=poster, amount=99999).error == "insufficient_balance"
    assert tools["blockchain_post_bounty"](poster_wallet="nobody", amount=1).error == "wallet_not_found"
    assert tools["blockchain_post_bounty"](poster_wallet=poster, amount=0).error == "invalid_amount"
    bounty = tools["blockchain_post_bounty"](poster_wallet=poster, amount=5, criteria={})
    assert bounty.ok and bounty.data.success
    bid = bounty.data.bounty_id
    assert tools["blockchain_claim_bounty"](bounty_id="missing", claimer_wallet=claimer).error == "bounty_not_found"
    assert tools["blockchain_claim_bounty"](bounty_id=bid, claimer_wallet="nobody").error == "wallet_not_found"
    assert tools["blockchain_claim_bounty"](bounty_id=bid, claimer_wallet=claimer).ok
    assert tools["blockchain_claim_bounty"](bounty_id=bid, claimer_wallet=claimer).error == "bounty_not_open"
    assert tools["blockchain_cancel_bounty"](bounty_id=bid).error == "bounty_not_cancellable"
    assert tools["blockchain_cancel_bounty"](bounty_id="missing").error == "bounty_not_found"


def test_transfer_and_mint_refusals_are_typed_codes() -> None:
    tools = _tools()
    a, b = _funded(tools, "ta", 5), _funded(tools, "tb", 0)
    assert tools["blockchain_transfer"](from_wallet=a, to_wallet=b, amount=50).error == "insufficient_balance"
    assert tools["blockchain_transfer"](from_wallet=a, to_wallet=b, amount=-1).error == "invalid_amount"
    assert tools["blockchain_transfer"](from_wallet="nobody", to_wallet=b, amount=1).error == "wallet_not_found"
    assert tools["blockchain_mint"](to_wallet="nobody", amount=1).error == "wallet_not_found"
    assert tools["blockchain_mint"](to_wallet=a, amount=0).error == "invalid_amount"
