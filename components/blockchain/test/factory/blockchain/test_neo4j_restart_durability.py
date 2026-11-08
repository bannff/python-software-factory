"""A restarted Neo4j ledger resumes the same chain, supply and wallets (#386).

An in-memory fake stands in for the graph brick: it implements only the four
graph tools the ledger calls, with upsert-by-id semantics.
"""
from __future__ import annotations

import pytest

from factory.blockchain.runtime.ledger import neo4j_bounty, neo4j_ledger, neo4j_rewards
from factory.blockchain.runtime.ledger.neo4j_bounty import Neo4jBountyMixin
from factory.blockchain.runtime.ledger.neo4j_ledger import Neo4jLedger


class FakeGraph:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}

    def __call__(self, tool: str, **kw):
        if tool == "graph_graph_add_entity":
            row = self.entities.setdefault(kw["entity_id"], {"type": kw["entity_type"], "props": {}})
            row["props"].update(kw.get("properties") or {})
            return {}
        if tool == "graph_graph_get_entity":
            row = self.entities.get(kw["entity_id"])
            return {"found": True, "properties": dict(row["props"])} if row else {"found": False}
        if tool == "graph_graph_find_entities":
            rows = [{"id": i, "properties": dict(r["props"])}
                    for i, r in self.entities.items() if r["type"] == kw["entity_type"]]
            return {"entities": rows[: kw.get("limit", 100)]}
        return {}  # relationships, health


class Ledger(Neo4jBountyMixin, Neo4jLedger):
    pass


@pytest.fixture
def graph(monkeypatch) -> FakeGraph:
    fake = FakeGraph()
    for module in (neo4j_ledger, neo4j_bounty, neo4j_rewards):
        if hasattr(module, "_invoke"):
            monkeypatch.setattr(module, "_invoke", fake)
    return fake


def test_blocks_supply_and_wallets_survive_a_restart(graph) -> None:
    first = Ledger(total_supply=1000.0)
    first.create_wallet("a")
    first.mint("wallet-a", 25.0)
    height, supply = first.get_chain_info().height, first.get_chain_info().total_supply
    assert supply == 1025.0

    second = Ledger(total_supply=1000.0)  # restart: same graph, same config
    info = second.get_chain_info()
    assert info.height == height and info.total_supply == supply
    assert second.get_balance("wallet-a") == 25.0
    assert second.verify_chain()["valid"] is True


def test_new_blocks_after_restart_extend_the_chain(graph) -> None:
    first = Ledger(total_supply=1000.0)
    first.create_wallet("a")
    first.mint("wallet-a", 5.0)
    second = Ledger(total_supply=1000.0)
    second.mint("wallet-a", 5.0)
    assert second.get_chain_info().height == first.get_chain_info().height + 1
    assert second.verify_chain()["valid"] is True
    assert Ledger(total_supply=1000.0).get_chain_info().total_supply == 1010.0


def test_health_reports_durability(graph) -> None:
    assert Ledger(total_supply=1.0).health_check().get("durable") is True
