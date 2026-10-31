"""Selector-free compatibility facade for the economy ledger profile."""
from __future__ import annotations

from typing import Mapping

from .composition import BlockchainComposition, BlockchainCompositionFactory
from .economy.runtime import EconomyProfileRuntime
from .ports import LedgerPort


class BlockchainRuntime:
    """Resolve trusted startup composition once and expose the economy ledger."""

    def __init__(self, adapter: str | None = None) -> None:
        """Build once; ``adapter`` is trusted direct-construction injection only."""
        composition, profile = BlockchainCompositionFactory(adapter).create()
        self._composition: BlockchainComposition = composition
        self._economy: EconomyProfileRuntime = profile  # type: ignore[assignment]

    @property
    def adapter_id(self) -> str:
        """Return the validated active economy adapter ID."""
        return self._composition.backend_id

    def get_ledger(self) -> LedgerPort:
        """Return the active economy ledger without profile selection."""
        return self._economy.ledger

    def capabilities(self) -> Mapping[str, object]:
        """Return only truthful active-economy capability facts."""
        return self._economy.capabilities()

    def health_check(self) -> Mapping[str, object]:
        """Return the active economy adapter health."""
        return self._economy.health_check()

    def config_schema(self) -> dict[str, object]:
        """Describe the finite trusted economy adapter configuration."""
        return {
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["mock", "neo4j", "mock_ledger"],
                    "description": "Economy ledger backend to use",
                },
                "total_supply": {
                    "type": "number",
                    "description": "Initial token supply for the economy",
                    "default": 1_000_000.0,
                },
            },
        }
