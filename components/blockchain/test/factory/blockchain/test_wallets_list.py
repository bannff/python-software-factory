from __future__ import annotations

import asyncio

from factory.blockchain.server import create_tool_catalog


def _tools():
    catalog = create_tool_catalog()
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


def test_list_wallets_and_owner_id_resolves_to_its_wallet() -> None:
    tools = _tools()
    created = tools["blockchain_create_wallet"](owner_id="carol", initial_balance=0)
    assert created.ok
    listed = tools["blockchain_list_wallets"]()
    assert listed.ok and any(w.owner_id == "carol" for w in listed.data.wallets)
    by_owner = tools["blockchain_get_balance"](wallet_id="carol")
    assert by_owner.data.wallet_id == "wallet-carol" and by_owner.data.balance == 0
    assert tools["blockchain_get_wallet"](wallet_id="carol").data.found
    assert tools["blockchain_list_wallets"](limit=1).data.count <= 1
