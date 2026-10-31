"""Trusted startup builder for the fixed economy-only composition."""
from __future__ import annotations

import os

from ..economy.runtime import EconomyProfileRuntimeFactory
from .models import BlockchainComposition, ProfileDefinition, ProfileRegistration

_CANONICAL_BACKENDS = ("mock", "neo4j")
_COMPATIBILITY_ALIASES = {"mock_ledger": "mock"}
_ECONOMY = ProfileRegistration(
    definition=ProfileDefinition("economy", "economy", mounted=True),
    backend_ids=_CANONICAL_BACKENDS,
)


class BlockchainCompositionFactory:
    """Build the immutable composition once from trusted process configuration."""

    def __init__(
        self, backend_id: str | None = None,
        registrations: tuple[ProfileRegistration, ...] = (_ECONOMY,),
    ) -> None:
        requested = backend_id or os.environ.get("BLOCKCHAIN_ADAPTER", "mock")
        self._backend_id = _COMPATIBILITY_ALIASES.get(requested, requested)
        self._registrations = registrations

    @property
    def backend_id(self) -> str:
        return self._backend_id

    def create(self) -> tuple[BlockchainComposition, object]:
        composition = BlockchainComposition.create(self._registrations, self._backend_id)
        runtime = EconomyProfileRuntimeFactory().create(backend_id=composition.backend_id)
        return composition, runtime


__all__ = ["BlockchainCompositionFactory", "_CANONICAL_BACKENDS", "_COMPATIBILITY_ALIASES"]
