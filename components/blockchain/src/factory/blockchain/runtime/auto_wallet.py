"""Auto-wallet creation for MCP clients.

Every principal that interacts with the blockchain gets a wallet
automatically. Identity comes from the envelope context.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ports import LedgerPort

logger = logging.getLogger(__name__)

_DEFAULT_INITIAL_BALANCE = 100.0


def get_or_create_wallet(
    ledger: "LedgerPort",
    principal_id: str | None = None,
    initial_balance: float = _DEFAULT_INITIAL_BALANCE,
) -> str:
    """Ensure the principal has a wallet. Returns wallet_id.

    If principal_id is None, attempts to read from envelope context.
    Creates wallet with initial_balance from treasury if new.
    """
    pid = principal_id or _resolve_principal()
    if not pid:
        raise ValueError("No principal_id provided and none in envelope context")
    wallet_id = f"wallet-{pid}"
    existing = ledger.get_wallet(wallet_id)
    if existing is not None:
        return wallet_id
    try:
        ledger.create_wallet(pid, initial_balance)
        logger.info("Auto-created wallet %s with %s tokens", wallet_id, initial_balance)
    except ValueError:
        pass  # Already exists (race condition)
    return wallet_id


def _resolve_principal() -> str | None:
    """Read principal_id from envelope context."""
    try:
        from factory.mcp_utils.interface import get_principal_id
        return get_principal_id()
    except Exception:
        return None
