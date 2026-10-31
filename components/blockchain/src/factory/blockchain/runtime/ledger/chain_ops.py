"""Block hashing, merkle trees, and chain verification.

Pure functions for hash-chained block operations.
Shared by MockLedger and future Neo4jLedgerAdapter.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..models import Block, _utcnow

_GENESIS_PREV = "0" * 64


def sha256(data: str) -> str:
    """SHA-256 hash of a string."""
    return hashlib.sha256(data.encode()).hexdigest()


def merkle_root(tx_ids: list[str]) -> str:
    """Compute merkle root from transaction IDs."""
    if not tx_ids:
        return sha256("")
    hashes = [sha256(tid) for tid in tx_ids]
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [
            sha256(hashes[i] + hashes[i + 1])
            for i in range(0, len(hashes), 2)
        ]
    return hashes[0]


def block_hash(height: int, prev: str, merkle: str, ts: str) -> str:
    """Compute block hash from its components."""
    return sha256(f"{height}:{prev}:{merkle}:{ts}")


def make_block(
    height: int, prev_hash: str, tx_ids: list[str],
) -> Block:
    """Create a new block with computed hashes."""
    ts = _utcnow()
    mr = merkle_root(tx_ids)
    h = block_hash(height, prev_hash, mr, ts)
    return Block(
        height=height, hash=h, prev_hash=prev_hash,
        merkle_root=mr, tx_ids=tx_ids, timestamp=ts,
    )


def verify_blocks(blocks: list[Block]) -> dict[str, Any]:
    """Walk the chain and verify hash integrity."""
    errors: list[str] = []
    for i, blk in enumerate(blocks):
        expected_prev = blocks[i - 1].hash if i > 0 else _GENESIS_PREV
        if blk.prev_hash != expected_prev:
            errors.append(f"Block {i}: prev_hash mismatch")
        expected = block_hash(
            blk.height, blk.prev_hash, blk.merkle_root, blk.timestamp,
        )
        if blk.hash != expected:
            errors.append(f"Block {i}: hash mismatch")
    return {
        "valid": len(errors) == 0,
        "blocks_checked": len(blocks),
        "errors": errors,
    }
