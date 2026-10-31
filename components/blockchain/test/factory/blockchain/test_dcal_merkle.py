"""Focused RFC-6962 Merkle vectors and adversarial DCAL proof checks."""
from __future__ import annotations

from itertools import repeat

import pytest

from factory.blockchain.runtime.dcal import merkle
from factory.blockchain.runtime.dcal.merkle import (
    MAX_SIBLINGS, MAX_TREE_SIZE, consistency_proof, empty_root, inclusion_proof, leaf_hash,
    merkle_root, node_hash, verify_consistency, verify_inclusion,
)

_ROWS = [b"a", b"b", b"c", b"d", b"e"]
_ROOTS = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "022a6979e6dab7aa5ae4c3e5e45f7e977112a7e63593820dbec1ec738a24f93c",
    "b137985ff484fb600db93107c77b0365c80d78f5b429ded0fd97361d077999eb",
    "36642e73c2540ab121e3a6bf9545b0a24982cd830eb13d3cd19de3ce6c021ec1",
    "33376a3bd63e9993708a84ddfe6c28ae58b83505dd1fed711bd924ec5a6239f0",
    "fe14a5426fbd70c0fa73f52342afed0da0bd23c4838662ccf6b88a3070ead97b",
)


def test_frozen_empty_one_odd_balanced_and_extension_roots() -> None:
    assert empty_root().hex() == _ROOTS[0]
    assert [merkle_root(_ROWS[:size]).hex() for size in range(6)] == list(_ROOTS)
    assert leaf_hash(b"a").hex() == _ROOTS[1]
    assert node_hash(leaf_hash(b"a"), leaf_hash(b"b")).hex() == _ROOTS[2]


@pytest.mark.parametrize("size", (1, 3, 4, 5))
def test_inclusion_proofs_verify_all_records_for_each_tree_shape(size: int) -> None:
    root = merkle_root(_ROWS[:size])
    for index, record in enumerate(_ROWS[:size]):
        proof = inclusion_proof(_ROWS[:size], index, size)
        assert verify_inclusion(record, index, size, proof, root)


def test_inclusion_proof_rejects_mutation_missing_surplus_reordering_and_bounds() -> None:
    root, proof = merkle_root(_ROWS[:4]), inclusion_proof(_ROWS[:4], 1, 4)
    changed = (bytes([proof[0][0] ^ 1]) + proof[0][1:], *proof[1:])
    assert not verify_inclusion(b"b", 1, 4, changed, root)
    assert not verify_inclusion(b"b", 1, 4, proof[:-1], root)
    assert not verify_inclusion(b"b", 1, 4, (*proof, proof[0]), root)
    assert not verify_inclusion(b"b", 1, 4, tuple(reversed(proof)), root)
    assert not verify_inclusion(b"b", 1, 4, (b"x",), root)
    assert not verify_inclusion(b"b", 1, 4, (b"x" * 32,) * (MAX_SIBLINGS + 1), root)


def test_consistency_proofs_verify_and_extension_is_frozen() -> None:
    old_root, new_root = merkle_root(_ROWS[:4]), merkle_root(_ROWS)
    proof = consistency_proof(_ROWS, 4, 5)
    assert [node.hex() for node in proof] == ["2824a7ccda2caa720c85c9fba1e8b5b735eecfdb03878e4f8dfe6c3625030bc4"]
    assert verify_consistency(4, 5, old_root, new_root, proof)
    assert verify_consistency(0, 5, empty_root(), new_root, ())


def test_consistency_rejects_mutation_missing_surplus_and_invalid_sizes() -> None:
    old_root, new_root = merkle_root(_ROWS[:3]), merkle_root(_ROWS[:4])
    proof = consistency_proof(_ROWS[:4], 3, 4)
    changed = (bytes([proof[0][0] ^ 1]) + proof[0][1:], *proof[1:])
    assert not verify_consistency(3, 4, old_root, new_root, changed)
    assert not verify_consistency(3, 4, old_root, new_root, proof[:-1])
    assert not verify_consistency(3, 4, old_root, new_root, tuple(reversed(proof)))
    assert not verify_consistency(3, 4, old_root, new_root, (*proof, proof[0]))
    assert not verify_consistency(4, 3, new_root, old_root, ())
    assert not verify_consistency(-1, 4, old_root, new_root, proof)
    assert not verify_consistency(3, 4, old_root, new_root, (b"x",))


@pytest.mark.parametrize("value", ("record", bytearray(b"record"), memoryview(b"record"), 1))
def test_non_bytes_records_and_malformed_nodes_are_rejected(value: object) -> None:
    with pytest.raises(TypeError):
        leaf_hash(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        merkle_root([value])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        node_hash(b"x" * 31, b"y" * 32)
    assert not verify_inclusion(value, 0, 1, (), merkle_root([b"a"]))  # type: ignore[arg-type]


def test_empty_tree_has_no_inclusion_proof() -> None:
    with pytest.raises(ValueError):
        inclusion_proof([], 0, 0)
    assert not verify_inclusion(b"a", 0, 0, (), empty_root())


def test_merkle_root_rejects_infinite_records_at_the_practical_cap(monkeypatch) -> None:
    monkeypatch.setattr(merkle, "MAX_RECORDS", 2)
    with pytest.raises(ValueError, match="tree exceeds maximum records"):
        merkle_root(repeat(b"record"))


@pytest.mark.parametrize(
    ("consumer", "expected_consumed"),
    (
        (lambda records: inclusion_proof(records, 0, 1), 2),
        (lambda records: consistency_proof(records, 1, 2), 3),
    ),
)
def test_proof_construction_rejects_surplus_without_over_consuming(
    consumer, expected_consumed: int,
) -> None:
    consumed = 0

    def infinite_records():
        nonlocal consumed
        while True:
            consumed += 1
            yield b"record"

    with pytest.raises(ValueError, match="tree size does not match records"):
        consumer(infinite_records())
    assert consumed == expected_consumed


def test_proof_sizes_are_validated_before_consuming_records() -> None:
    def fail_if_consumed():
        raise AssertionError("records should not be consumed")
        yield b"record"

    for consumer in (
        lambda records: inclusion_proof(records, 0, merkle.MAX_RECORDS + 1),
        lambda records: consistency_proof(records, 1, merkle.MAX_RECORDS + 1),
    ):
        with pytest.raises(ValueError, match="tree exceeds maximum records"):
            consumer(fail_if_consumed())


def test_verification_retains_rfc_tree_size_support() -> None:
    assert verify_consistency(0, MAX_TREE_SIZE, empty_root(), b"x" * 32, ())


def test_infinite_proofs_are_rejected_at_the_sibling_bound(monkeypatch) -> None:
    monkeypatch.setattr(merkle, "MAX_SIBLINGS", 2)
    old_root, new_root = merkle_root(_ROWS[:1]), merkle_root(_ROWS[:2])
    infinite_proof = repeat(b"x" * 32)
    assert not verify_inclusion(b"a", 0, 2, infinite_proof, new_root)
    assert not verify_consistency(1, 2, old_root, new_root, repeat(b"x" * 32))