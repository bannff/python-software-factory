"""The Neo4j ledger reads the aggregator's v1 envelope, not the inner shape (#423)."""
from __future__ import annotations

import pytest

from factory.blockchain.runtime.errors import LedgerError
from factory.blockchain.runtime.ledger import neo4j_ledger
from factory.blockchain.runtime.ledger.neo4j_bounty import Neo4jBountyMixin
from factory.blockchain.runtime.ledger.neo4j_ledger import Neo4jLedger


class FakeGraph:
    """Upsert-by-id graph returning the brick's inner payload shape."""

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}

    def __call__(self, tool: str, **kw):
        if tool == "graph_graph_add_entity":
            row = self.entities.setdefault(kw["entity_id"], {"type": kw["entity_type"], "props": {}})
            row["props"].update(kw.get("properties") or {})
        elif tool == "graph_graph_get_entity":
            row = self.entities.get(kw["entity_id"])
            return {"found": True, "properties": dict(row["props"])} if row else {"found": False}
        elif tool == "graph_graph_find_entities":
            rows = [{"id": i, "properties": dict(r["props"])}
                    for i, r in self.entities.items() if r["type"] == kw["entity_type"]]
            return {"entities": rows[: kw.get("limit", 100)]}
        return {}


class EnvelopeAggregator:
    """Wraps the inner-shape fake the way ``MCPAggregator.invoke_tool`` does."""

    def __init__(self) -> None:
        self.graph = FakeGraph()

    def invoke_tool(self, tool: str, **kw):
        if tool == "graph_graph_health_check":
            return {"schema_version": "v1", "ok": True, "data": {"healthy": True}}
        return {"schema_version": "v1", "ok": True, "data": self.graph(tool, **kw)}


class Ledger(Neo4jBountyMixin, Neo4jLedger):
    pass


@pytest.fixture
def agg(monkeypatch) -> EnvelopeAggregator:
    fake = EnvelopeAggregator()
    monkeypatch.setattr(neo4j_ledger, "_get_aggregator", lambda: fake)
    return fake


def test_second_construction_adopts_chain_and_is_healthy(agg) -> None:
    first = Ledger(total_supply=1000.0)
    first.create_wallet("a")
    genesis = first.get_chain_info().genesis_hash
    second = Ledger(total_supply=1000.0)
    assert second.get_chain_info().genesis_hash == genesis
    assert len(second.list_wallets()) == len(first.list_wallets()) >= 2
    assert second.health_check()["healthy"] is True
    blocks = [e for e in agg.graph.entities.values() if e["type"] == "Block"]
    assert len(blocks) == len(first._blocks)


def test_failed_envelope_raises_typed_error(monkeypatch) -> None:
    class Failing:
        def invoke_tool(self, tool, **kw):
            return {"ok": False, "error": "boom"}
    monkeypatch.setattr(neo4j_ledger, "_get_aggregator", lambda: Failing())
    with pytest.raises(LedgerError):
        neo4j_ledger._invoke("graph_graph_get_entity", entity_id="x")
