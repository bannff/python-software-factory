from __future__ import annotations

from factory.blockchain.mcp.dashboard_activity import recent_activity

ENTRY = {
    "event_id": "e1", "event_type": "blockchain.tx.committed", "timestamp": "2026-11-02T00:00:00Z",
    "payload": {"tx_id": "tx-1", "tx_type": "mint", "amount": 7, "to_wallet": "wallet-a"},
}


def test_plain_dict_payload_from_the_aggregator_is_projected() -> None:
    rows = recent_activity(lambda *_a, **_k: {"entries": [ENTRY], "total": 1}, 10, None, None, None)
    assert [r["tx_id"] for r in rows] == ["tx-1"] and rows[0]["label"] == "Transaction Committed"


def test_filters_still_apply_and_failures_stay_empty() -> None:
    invoker = lambda *_a, **_k: {"entries": [ENTRY]}
    assert recent_activity(invoker, 10, "other", None, None) == []
    assert recent_activity(invoker, 10, None, None, "wallet-a")[0]["tx_id"] == "tx-1"
    def boom(*_a, **_k):
        raise RuntimeError("down")
    assert recent_activity(boom, 10, None, None, None) == []
