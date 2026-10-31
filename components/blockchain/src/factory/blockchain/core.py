"""Blockchain core — high-level convenience functions.

Simple API for common operations without managing the full
BlockchainRuntime lifecycle.
"""

from __future__ import annotations

from typing import Any

_runtime: "BlockchainRuntime | None" = None


def get_runtime() -> "BlockchainRuntime":
    """Get or create the default BlockchainRuntime instance."""
    global _runtime
    if _runtime is None:
        from .runtime.runtime import BlockchainRuntime
        _runtime = BlockchainRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime instance (for testing)."""
    global _runtime
    _runtime = None


def create_wallet(owner_id: str, initial_balance: float = 0) -> dict[str, Any]:
    """Create a wallet and return its data."""
    wallet = get_runtime().get_ledger().create_wallet(owner_id, initial_balance)
    return wallet.model_dump()


def transfer(
    from_wallet: str, to_wallet: str, amount: float, memo: str = "",
) -> dict[str, Any]:
    """Transfer tokens between wallets."""
    tx = get_runtime().get_ledger().transfer(from_wallet, to_wallet, amount, memo)
    return tx.model_dump()


def get_balance(wallet_id: str) -> float:
    """Get current balance for a wallet."""
    return get_runtime().get_ledger().get_balance(wallet_id)


def health_check() -> dict[str, Any]:
    """Check blockchain service health."""
    return get_runtime().get_ledger().health_check()
