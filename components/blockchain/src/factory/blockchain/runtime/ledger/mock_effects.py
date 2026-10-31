"""Injected observable effects for MockLedger operations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..models import Block, Bounty, Transaction, Wallet


@dataclass(frozen=True)
class LedgerEffects:
    """Effect ports kept injectable so the legacy module patch seams remain live."""

    sync_wallet: Callable[[Wallet], None]
    sync_transaction: Callable[[Transaction], None]
    sync_block: Callable[[Block], None]
    sync_bounty: Callable[[Bounty], None]
    emit: Callable[[str, dict], None]
