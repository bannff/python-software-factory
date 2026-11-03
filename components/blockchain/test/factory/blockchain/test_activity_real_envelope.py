from __future__ import annotations

import asyncio

from factory.blockchain.mcp.dashboard_activity import recent_activity
from factory.events.server import create_tool_catalog


def test_real_events_tool_output_dumped_like_the_aggregator_is_projected() -> None:
    tools = {t.name: t.fn for t in asyncio.run(create_tool_catalog().list_tools())}
    tools["events_publish"](
        source="blockchain", event_type="blockchain.tx.committed",
        payload={"tx_id": "tx-9", "tx_type": "mint", "amount": 3, "to_wallet": "wallet-a"})
    # The aggregator hands callers structured_content: the ToolResult serialised to a dict.
    envelope = tools["events_query_history"](source="blockchain", limit=10).model_dump(mode="json")
    assert envelope["ok"] and "entries" not in envelope  # entries are nested under data
    rows = recent_activity(lambda *_a, **_k: envelope, 10, None, None, None)
    assert [r["tx_id"] for r in rows] == ["tx-9"]
