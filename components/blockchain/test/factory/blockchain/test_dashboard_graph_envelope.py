"""Graph context must unwrap the aggregator's {ok, data} envelope (issue #370)."""
from __future__ import annotations

from factory.blockchain.mcp.dashboard_graph import related_graph_entities

ENTITY = {"id": "tx-1", "type": "Transaction", "properties": {"tx_id": "tx-1", "status": "confirmed"}}
NEIGHBOR = {"id": "w-1", "type": "Wallet", "properties": {"wallet_id": "w-1"}}


def _envelope(data: dict) -> dict:
    return {"schema_version": "v1", "ok": True, "data": data}


def test_rows_come_from_enveloped_entity_and_neighbors() -> None:
    def invoker(tool, **kwargs):
        if tool == "graph_graph_get_entity":
            return _envelope({"found": True, "entity_id": "tx-1", "entity": ENTITY})
        return _envelope({"entity_id": "tx-1", "neighbors": [NEIGHBOR], "count": 1})

    rows = related_graph_entities(invoker, 10, "tx-1", None, None)
    assert [r["entity_id"] for r in rows] == ["tx-1", "w-1"]
    assert rows[0]["subtitle"] == "confirmed"


def test_not_found_and_failed_envelopes_yield_no_rows() -> None:
    def invoker(tool, **kwargs):
        if tool == "graph_graph_get_entity":
            return _envelope({"found": False, "entity_id": "tx-1", "entity": None})
        return {"schema_version": "v1", "ok": False, "error": "tool_execution_failed"}

    assert related_graph_entities(invoker, 10, "tx-1", None, None) == []


def test_bare_payloads_still_work() -> None:
    def invoker(tool, **kwargs):
        if tool == "graph_graph_get_entity":
            return ENTITY
        return {"neighbors": [NEIGHBOR]}

    rows = related_graph_entities(invoker, 10, "tx-1", None, None)
    assert [r["entity_id"] for r in rows] == ["tx-1", "w-1"]
