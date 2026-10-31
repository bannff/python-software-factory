"""Pure, unregistered RFC-6962 Merkle helpers for DCAL evidence commitments."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from itertools import islice

MAX_SIBLINGS = 64
MAX_TREE_SIZE = 1 << MAX_SIBLINGS
MAX_RECORDS = 4096
_EMPTY_ROOT = hashlib.sha256(b"").digest()


def leaf_hash(record_bytes: bytes) -> bytes:
    """Return the RFC-6962 leaf hash for one byte record."""
    if not isinstance(record_bytes, bytes):
        raise TypeError("record must be bytes")
    return hashlib.sha256(b"\x00" + record_bytes).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """Return the RFC-6962 interior-node hash for two 32-byte child hashes."""
    _node(left)
    _node(right)
    return hashlib.sha256(b"\x01" + left + right).digest()


def empty_root() -> bytes:
    """Return the defined empty-tree root."""
    return _EMPTY_ROOT


def merkle_root(records: Iterable[bytes]) -> bytes:
    """Build the RFC-6962 root using largest-power-of-two splits."""
    leaves = _records(records)
    return _root(leaves)


def inclusion_proof(records: Iterable[bytes], leaf_index: int, tree_size: int) -> tuple[bytes, ...]:
    """Construct the bounded inclusion proof for ``leaf_index`` in ``tree_size`` records."""
    _position(leaf_index, tree_size)
    leaves = _records(records, tree_size)
    proof = _inclusion(leaves, leaf_index)
    _bounded(proof)
    return tuple(proof)


def verify_inclusion(
    record: bytes, leaf_index: int, tree_size: int, proof: Iterable[bytes], root: bytes,
) -> bool:
    """Verify a bounded RFC-6962 inclusion proof without raising on malformed input."""
    try:
        _position(leaf_index, tree_size)
        _node(root)
        siblings = iter(_proof(proof))
        current = _verify_inclusion(leaf_hash(record), leaf_index, tree_size, siblings)
        return current == root and next(siblings, None) is None
    except (StopIteration, TypeError, ValueError):
        return False


def consistency_proof(records: Iterable[bytes], old_size: int, new_size: int) -> tuple[bytes, ...]:
    """Construct a bounded proof that the old tree is a prefix of the new tree."""
    _sizes(old_size, new_size)
    leaves = _records(records, new_size)
    if old_size in (0, new_size):
        return ()
    proof = _consistency(leaves[:new_size], old_size, True)
    _bounded(proof)
    return tuple(proof)


def verify_consistency(
    old_size: int, new_size: int, old_root: bytes, new_root: bytes, proof: Iterable[bytes],
) -> bool:
    """Verify a bounded RFC-6962 consistency proof without raising on malformed input."""
    try:
        _sizes(old_size, new_size)
        _node(old_root)
        _node(new_root)
        siblings = _proof(proof)
        if old_size == 0:
            return not siblings and old_root == _EMPTY_ROOT
        if old_size == new_size:
            return not siblings and old_root == new_root
        fn, sn = old_size - 1, new_size - 1
        while fn & 1:
            fn, sn = fn >> 1, sn >> 1
        if not siblings:
            return False
        fr = sr = siblings[0] if fn else old_root
        start = 1 if fn else 0
        for sibling in siblings[start:]:
            if sn == 0:
                return False
            if fn & 1 or fn == sn:
                fr, sr = node_hash(sibling, fr), node_hash(sibling, sr)
                while fn and not (fn & 1):
                    fn, sn = fn >> 1, sn >> 1
            else:
                sr = node_hash(sr, sibling)
            fn, sn = fn >> 1, sn >> 1
        return sn == 0 and fr == old_root and sr == new_root
    except (TypeError, ValueError):
        return False


def _records(records: Iterable[bytes], expected_size: int | None = None) -> list[bytes]:
    limit = MAX_RECORDS if expected_size is None else expected_size
    if limit > MAX_RECORDS:
        raise ValueError("tree exceeds maximum records")
    values = list(islice(records, limit + 1))
    if len(values) > limit:
        raise ValueError("tree exceeds maximum records" if expected_size is None else "tree size does not match records")
    if expected_size is not None and len(values) != expected_size:
        raise ValueError("tree size does not match records")
    if any(not isinstance(value, bytes) for value in values):
        raise TypeError("records must be bytes")
    return [leaf_hash(value) for value in values]


def _root(leaves: Sequence[bytes]) -> bytes:
    if not leaves:
        return _EMPTY_ROOT
    if len(leaves) == 1:
        return leaves[0]
    split = _split(len(leaves))
    return node_hash(_root(leaves[:split]), _root(leaves[split:]))


def _inclusion(leaves: Sequence[bytes], index: int) -> list[bytes]:
    if len(leaves) == 1:
        return []
    split = _split(len(leaves))
    if index < split:
        return _inclusion(leaves[:split], index) + [_root(leaves[split:])]
    return _inclusion(leaves[split:], index - split) + [_root(leaves[:split])]


def _consistency(leaves: Sequence[bytes], old_size: int, complete: bool) -> list[bytes]:
    if old_size == len(leaves):
        return [] if complete else [_root(leaves)]
    split = _split(len(leaves))
    if old_size <= split:
        return _consistency(leaves[:split], old_size, complete) + [_root(leaves[split:])]
    return _consistency(leaves[split:], old_size - split, False) + [_root(leaves[:split])]


def _verify_inclusion(current: bytes, index: int, size: int, siblings: Iterable[bytes]) -> bytes:
    if size == 1:
        return current
    split = _split(size)
    if index < split:
        left = _verify_inclusion(current, index, split, siblings)
        return node_hash(left, next(siblings))
    right = _verify_inclusion(current, index - split, size - split, siblings)
    return node_hash(next(siblings), right)


def _split(size: int) -> int:
    return 1 << ((size - 1).bit_length() - 1)


def _node(value: object) -> None:
    if not isinstance(value, bytes) or len(value) != 32:
        raise TypeError("node hashes must be 32-byte bytes")


def _position(index: int, size: int, actual: int | None = None) -> None:
    _sizes(size, size, actual)
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < size:
        raise ValueError("invalid leaf index")


def _sizes(old_size: int, new_size: int, actual: int | None = None) -> None:
    if any(not isinstance(size, int) or isinstance(size, bool) for size in (old_size, new_size)):
        raise TypeError("tree sizes must be integers")
    if not 0 <= old_size <= new_size <= MAX_TREE_SIZE:
        raise ValueError("invalid tree sizes")
    if actual is not None and actual != new_size:
        raise ValueError("tree size does not match records")


def _proof(proof: Iterable[bytes]) -> list[bytes]:
    values = list(islice(proof, MAX_SIBLINGS + 1))
    _bounded(values)
    return values


def _bounded(nodes: Sequence[bytes]) -> None:
    if len(nodes) > MAX_SIBLINGS:
        raise ValueError("proof exceeds maximum siblings")
    for value in nodes:
        _node(value)
