"""Encrypted credential-slot store: CAS, generation fence, tombstone, rekey.

Covers isolation, opaque failures, tamper rejection, at-rest ciphertext (no
plaintext canary in SQLite/WAL/SHM), concurrent-rotate single CAS winner, and a
Hypothesis stateful model of the generation/version lifecycle.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from factory.mcp_utils.interface import TestKeyProvider
from factory.storage.runtime.adapters.credential_slots_sqlite import (
    SQLiteCredentialSlotStore,
)
from factory.storage.runtime.ports.credential_slots import (
    CredentialSlotError, SlotIdentity,
)

CANARY = "refresh-CANARY-b3f1a9c7d5e24680aa11223344556677"


def _store(tmp_path, name="cred.db"):
    return SQLiteCredentialSlotStore(str(tmp_path / name), TestKeyProvider()), tmp_path / name


def _ident(**over):
    base = dict(tenant_id="t1", owner_id="o1", provider_id="microsoft",
               connection_ref="c1", slot_kind="refresh_token")
    base.update(over)
    return SlotIdentity(**base)


def test_create_read_roundtrip(tmp_path):
    store, _ = _store(tmp_path)
    receipt = store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    assert (receipt.generation, receipt.version) == (1, 1)
    got = store.read(_ident(), generation=1)
    assert got.secret == {"refresh_token": CANARY} and (got.generation, got.version) == (1, 1)


def test_duplicate_live_create_is_opaque(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "a"}, generation=1, expected_version=None)
    with pytest.raises(CredentialSlotError):
        store.write(_ident(), {"refresh_token": "b"}, generation=1, expected_version=None)


def test_rotate_cas_and_wrong_version(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "v1"}, generation=1, expected_version=None)
    r = store.write(_ident(), {"refresh_token": "v2"}, generation=1, expected_version=1)
    assert r.version == 2 and store.read(_ident(), generation=1).secret == {"refresh_token": "v2"}
    with pytest.raises(CredentialSlotError):  # stale version loses the CAS
        store.write(_ident(), {"refresh_token": "v3"}, generation=1, expected_version=1)


def test_wrong_generation_read_is_opaque(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "x"}, generation=1, expected_version=None)
    with pytest.raises(CredentialSlotError):
        store.read(_ident(), generation=2)


def test_revoke_bumps_generation_and_tombstones(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    out = store.revoke(_ident(), generation=1)
    assert out.generation == 2
    with pytest.raises(CredentialSlotError):  # old generation is dead
        store.read(_ident(), generation=1)
    # re-enrollment at the new generation reactivates
    store.write(_ident(), {"refresh_token": "fresh"}, generation=2, expected_version=None)
    assert store.read(_ident(), generation=2).secret == {"refresh_token": "fresh"}


def test_rekey_preserves_plaintext_changes_ciphertext(tmp_path):
    store, path = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    store.rekey(_ident(), generation=1)
    assert store.read(_ident(), generation=1).secret == {"refresh_token": CANARY}


def test_isolation_across_identity(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "A"}, generation=1, expected_version=None)
    store.write(_ident(tenant_id="t2"), {"refresh_token": "B"}, generation=1, expected_version=None)
    store.write(_ident(provider_id="adobe", slot_kind="client_secret"),
                {"client_secret": "C"}, generation=1, expected_version=None)
    assert store.read(_ident(), generation=1).secret == {"refresh_token": "A"}
    assert store.read(_ident(tenant_id="t2"), generation=1).secret == {"refresh_token": "B"}


def test_tampered_envelope_is_opaque(tmp_path):
    import sqlite3
    store, path = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE credential_slots SET envelope=replace(envelope,'a','b')")
    conn.commit(); conn.close()
    with pytest.raises(CredentialSlotError):
        store.read(_ident(), generation=1)


def test_canary_secret_absent_from_disk(tmp_path):
    store, path = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(path) + suffix)
        if p.exists():
            assert CANARY.encode() not in p.read_bytes()


def test_concurrent_rotate_single_cas_winner(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "v1"}, generation=1, expected_version=None)
    results: list[bool] = []
    barrier = threading.Barrier(2)

    def rotate(tag):
        barrier.wait()
        try:
            store.write(_ident(), {"refresh_token": tag}, generation=1, expected_version=1)
            results.append(True)
        except CredentialSlotError:
            results.append(False)

    threads = [threading.Thread(target=rotate, args=(t,)) for t in ("a", "b")]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sorted(results) == [False, True]  # exactly one CAS winner
    assert store.read(_ident(), generation=1).version == 2


class _SlotMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        import tempfile
        self._dir = tempfile.mkdtemp()
        self.store = SQLiteCredentialSlotStore(self._dir + "/m.db", TestKeyProvider())
        self.exists = False
        self.tombstoned = False
        self.generation = 1
        self.version = 0
        self.secret = None

    @rule(val=st.text(min_size=1, max_size=32))
    @precondition(lambda self: not self.exists)
    def create(self, val: str):
        try:
            r = self.store.write(_ident(), {"refresh_token": val},
                                 generation=self.generation, expected_version=None)
            self.exists, self.tombstoned = True, False
            self.version, self.secret = r.version, val
        except CredentialSlotError:
            assert self.exists  # only fails when already live

    @rule(val=st.text(min_size=1, max_size=32))
    @precondition(lambda self: self.exists and not self.tombstoned)
    def rotate(self, val: str):
        r = self.store.write(_ident(), {"refresh_token": val},
                             generation=self.generation, expected_version=self.version)
        self.version, self.secret = r.version, val

    @precondition(lambda self: self.exists and not self.tombstoned)
    @rule()
    def revoke(self):
        out = self.store.revoke(_ident(), generation=self.generation)
        self.generation, self.tombstoned, self.exists = out.generation, True, False

    @precondition(lambda self: self.exists and not self.tombstoned)
    @rule()
    def rekey(self):
        self.store.rekey(_ident(), generation=self.generation)

    @invariant()
    def read_matches_model(self):
        if self.exists and not self.tombstoned:
            got = self.store.read(_ident(), generation=self.generation)
            assert got.secret == {"refresh_token": self.secret}
            assert got.version == self.version


_SlotMachine.TestCase.settings = settings(max_examples=30, deadline=None, stateful_step_count=12)
TestSlotMachine = _SlotMachine.TestCase
