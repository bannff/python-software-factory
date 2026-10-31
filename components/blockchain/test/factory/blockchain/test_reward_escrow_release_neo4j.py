"""S4b guard: graph-backend released escrows are terminal (no re-escrow).

A redelivered non-GT reward.computed after release must not re-escrow on the
graph backend — that would upsert the escrow record back to "escrowed" and
let the next eval projection double-credit the wallet. Mirrors the mock
backend contract (one wallet movement per run, ever).
"""
from types import SimpleNamespace

from factory.blockchain.runtime.ledger.neo4j_rewards import Neo4jRewardMixin


class FakeGraphNeo4jLedger(Neo4jRewardMixin):
    """Neo4jLedger port of the escrow mixin with an in-memory entity store."""

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.wallets = {"wallet-agent": {"balance": 0.0}}
        self.make_tx_calls = 0

    # Neo4jLedger seams used by the mixin
    def _make_tx(self, tx_type, from_w, to_w, amount, memo):
        self.make_tx_calls += 1
        return SimpleNamespace(tx_id=f"tx-{self.make_tx_calls}")

    def _commit_block(self, tx_ids: list[str]) -> None:
        pass

    def _get_wallet_props(self, wid: str) -> dict | None:
        return self.wallets.get(wid)

    def _update_wallet_balance(self, wid: str, new_balance: float) -> None:
        self.wallets[wid] = {"balance": new_balance}

    def get_reward_escrow(self, run_id: str) -> dict | None:
        # Emulate persistent graph truth: entity entities are authoritative.
        return self.entities.get(f"reward-escrow-{run_id}")


def _holdings(fake: FakeGraphNeo4jLedger) -> float:
    return float(fake.wallets["wallet-agent"]["balance"])


def test_graph_released_escrow_blocks_reescrow(monkeypatch) -> None:
    """released → re-escrow is a no-op: status stays released, one movement."""
    fake = FakeGraphNeo4jLedger()
    escrow_id = "reward-escrow-run-graph"
    monkeypatch.setattr(
        "factory.blockchain.runtime.ledger.neo4j_rewards._add_entity",
        lambda eid, etype, props: fake.entities.__setitem__(eid, dict(props)),
    )

    fake.escrow_reward("run-graph", "wallet-agent", 25.0, "RL:IDOR")
    assert fake.entities[escrow_id]["status"] == "escrowed"
    assert _holdings(fake) == 0.0

    released = fake.release_reward("run-graph")
    assert released["status"] == "released"
    assert _holdings(fake) == 25.0

    again = fake.escrow_reward("run-graph", "wallet-agent", 25.0, "RL:IDOR")
    assert again["status"] == "released", "re-escrow must return the released record untouched"
    assert fake.entities[escrow_id]["status"] == "released"
    assert fake.make_tx_calls == 2, "no new escrow transaction after release"
    assert _holdings(fake) == 25.0, "redelivery must not move the wallet again"

    release_again = fake.release_reward("run-graph")
    assert release_again.get("already_released") is True
    assert _holdings(fake) == 25.0


def test_graph_reescrow_without_release_keeps_single_escrow(monkeypatch) -> None:
    """Pre-release redelivery idempotency is preserved on the graph backend."""
    fake = FakeGraphNeo4jLedger()
    monkeypatch.setattr(
        "factory.blockchain.runtime.ledger.neo4j_rewards._add_entity",
        lambda eid, etype, props: fake.entities.__setitem__(eid, dict(props)),
    )
    first = fake.escrow_reward("run-graph", "wallet-agent", 25.0, "RL:IDOR")
    second = fake.escrow_reward("run-graph", "wallet-agent", 25.0, "RL:IDOR")
    assert first["escrow_tx_id"] == second["escrow_tx_id"]
    assert fake.make_tx_calls == 1
    assert fake.release_reward("run-graph")["status"] == "released"
    assert _holdings(fake) == 25.0
