"""Core models for blockchain agent economy.

Wallet/transaction/bounty model backed by hash-chained blocks.
No Fabric concepts — this is a private ledger for internal agent currency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"


class TransactionType(str, Enum):
    TRANSFER = "transfer"
    MINT = "mint"
    BOUNTY_ESCROW = "bounty_escrow"
    BOUNTY_RELEASE = "bounty_release"


class BountyStatus(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Wallet(BaseModel):
    """Agent wallet with token balance."""
    wallet_id: str = Field(..., description="Unique wallet ID (wallet-{owner_id})")
    owner_id: str = Field(..., description="Owner agent/user ID")
    balance: float = Field(default=0.0, description="Current token balance")
    created_at: str = Field(default_factory=_utcnow)


class Transaction(BaseModel):
    """A ledger transaction."""
    tx_id: str = Field(..., description="Transaction hash")
    tx_type: TransactionType = Field(..., description="Transaction type")
    from_wallet: str | None = Field(default=None, description="Sender wallet ID")
    to_wallet: str | None = Field(default=None, description="Receiver wallet ID")
    amount: float = Field(..., description="Token amount")
    memo: str = Field(default="", description="Human-readable memo")
    status: TransactionStatus = Field(default=TransactionStatus.COMMITTED)
    block_height: int | None = Field(default=None, description="Block containing this tx")
    created_at: str = Field(default_factory=_utcnow)


class Block(BaseModel):
    """A hash-chained block."""
    height: int = Field(..., description="Block height (0 = genesis)")
    hash: str = Field(..., description="SHA-256 hash of block contents")
    prev_hash: str = Field(..., description="Hash of previous block")
    merkle_root: str = Field(..., description="Merkle root of transaction hashes")
    tx_ids: list[str] = Field(default_factory=list, description="Transaction IDs")
    timestamp: str = Field(default_factory=_utcnow)


class Bounty(BaseModel):
    """A posted bounty with escrowed tokens."""
    bounty_id: str = Field(..., description="Unique bounty ID")
    poster_wallet: str = Field(..., description="Wallet that posted the bounty")
    amount: float = Field(..., description="Escrowed token amount")
    description: str = Field(default="", description="What the bounty is for")
    criteria: dict = Field(default_factory=dict, description="Completion criteria")
    status: BountyStatus = Field(default=BountyStatus.OPEN)
    claimer_wallet: str | None = Field(default=None, description="Wallet that claimed")
    escrow_tx_id: str | None = Field(default=None, description="Escrow transaction ID")
    release_tx_id: str | None = Field(default=None, description="Release transaction ID")
    created_at: str = Field(default_factory=_utcnow)


class ChainInfo(BaseModel):
    """Summary of chain state."""
    height: int = Field(default=0)
    total_supply: float = Field(default=0.0)
    wallet_count: int = Field(default=0)
    tx_count: int = Field(default=0)
    bounty_count: int = Field(default=0)
    genesis_hash: str = Field(default="")
