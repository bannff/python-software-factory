"""Economy profile runtime and its trusted backend construction."""
from __future__ import annotations

from typing import Mapping

from ..ports import LedgerPort


class EconomyProfileRuntime:
    """Economy-only profile; adapters are persistence choices, not profiles."""

    def __init__(self, ledger: LedgerPort, backend_id: str) -> None:
        self.ledger = ledger
        self.backend_id = backend_id

    def capabilities(self) -> Mapping[str, object]:
        return {
            "name": "blockchain",
            "version": "2.0.0",
            "features": ["agent_economy", "wallets", "bounties", "hash_chain"],
            "backends": ["mock", "neo4j"],
        }

    def health_check(self) -> Mapping[str, object]:
        return self.ledger.health_check()


class EconomyProfileRuntimeFactory:
    """Creates the economy profile from a validated canonical backend ID."""

    def create(self, *, backend_id: str) -> EconomyProfileRuntime:
        if backend_id == "mock":
            from ..ledger.mock_ledger import MockLedger

            return EconomyProfileRuntime(MockLedger(), backend_id)
        if backend_id == "neo4j":
            from ..ledger.neo4j_bounty import Neo4jBountyMixin
            from ..ledger.neo4j_ledger import Neo4jLedger

            class Neo4jLedgerFull(Neo4jBountyMixin, Neo4jLedger):
                """Economy ledger composed with bounty and chain queries."""

            return EconomyProfileRuntime(Neo4jLedgerFull(), backend_id)
        raise ValueError(f"Unsupported validated economy backend: {backend_id}")
