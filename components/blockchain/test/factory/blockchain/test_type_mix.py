from __future__ import annotations

import asyncio

from factory.blockchain.server import create_tool_catalog


def _tools():
    catalog = create_tool_catalog()
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}



def test_type_mix_counts_match_the_transactions() -> None:
    tools = _tools()
    tools["blockchain_create_wallet"](owner_id="mix-a")
    tools["blockchain_create_wallet"](owner_id="mix-b")
    tools["blockchain_mint"](to_wallet="wallet-mix-a", amount=10)
    tools["blockchain_transfer"](from_wallet="wallet-mix-a", to_wallet="wallet-mix-b", amount=3)
    series = {s["label"]: s["value"] for s in tools["blockchain_get_dashboard_summary"]().data.series}
    assert series["Mint"] >= 1 and series["Transfer"] >= 1
