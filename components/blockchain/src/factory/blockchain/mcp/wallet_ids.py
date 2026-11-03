"""Accept an owner id wherever a wallet id is expected."""
from __future__ import annotations

from typing import Any


def resolve_wallet_id(ledger: Any, ident: str) -> str:
    """Return ``ident`` if it names a wallet, else ``wallet-<ident>`` if that does.

    ``blockchain_create_wallet`` is keyed by owner but yields ``wallet-<owner>``;
    callers reasonably pass the owner back. Unknown ids pass through unchanged so
    the ledger's own not-found error still applies.
    """
    if ledger.get_wallet(ident) is not None:
        return ident
    prefixed = f"wallet-{ident}"
    return prefixed if ledger.get_wallet(prefixed) is not None else ident
