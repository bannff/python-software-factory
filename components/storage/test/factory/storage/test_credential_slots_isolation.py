"""Slot READ-level isolation + AAD replay/rollback rejection.

Complements test_credential_slots.py (which tests write-side isolation and
tamper). Here we prove that a decrypt is refused when the READ coordinate does
not match the stored identity (wrong tenant / owner), and that identity- and
version-bound AAD defeats ciphertext replay: an old-but-authentic envelope
cannot be decrypted under an advanced version fence or a foreign identity.
"""
from __future__ import annotations

import sqlite3

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.mcp_utils.interface import TestKeyProvider
from factory.storage.runtime.adapters.credential_slots_sqlite import (
    SQLiteCredentialSlotStore,
)
from factory.storage.runtime.ports.credential_slots import (
    CredentialSlotError, SlotIdentity,
)

CANARY = "refresh-CANARY-isolation-aa11bb22cc33dd44ee55"


def _store(tmp_path):
    path = tmp_path / "iso.db"
    return SQLiteCredentialSlotStore(str(path), TestKeyProvider()), path


def _ident(**over):
    base = dict(tenant_id="t1", owner_id="o1", provider_id="microsoft",
                connection_ref="c1", slot_kind="refresh_token")
    base.update(over)
    return SlotIdentity(**base)


def _envelope(path, ident):
    conn = sqlite3.connect(str(path))
    try:
        where = " AND ".join(f"{c}=?" for c in
                             ("tenant_id", "owner_id", "provider_id", "connection_ref", "slot_kind"))
        key = (ident.tenant_id, ident.owner_id, ident.provider_id,
               ident.connection_ref, ident.slot_kind)
        return conn.execute(
            f"SELECT envelope FROM credential_slots WHERE {where}", key).fetchone()[0]
    finally:
        conn.close()


def _set_envelope(path, ident, envelope):
    conn = sqlite3.connect(str(path))
    try:
        where = " AND ".join(f"{c}=?" for c in
                             ("tenant_id", "owner_id", "provider_id", "connection_ref", "slot_kind"))
        key = (ident.tenant_id, ident.owner_id, ident.provider_id,
               ident.connection_ref, ident.slot_kind)
        conn.execute(
            f"UPDATE credential_slots SET envelope=? WHERE {where}", (envelope, *key))
        conn.commit()
    finally:
        conn.close()


def test_read_with_wrong_tenant_is_opaque(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    with pytest.raises(CredentialSlotError):
        store.read(_ident(tenant_id="t2"), generation=1)


def test_read_with_wrong_owner_is_opaque(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    with pytest.raises(CredentialSlotError):
        store.read(_ident(owner_id="o2"), generation=1)


def test_read_with_wrong_connection_is_opaque(tmp_path):
    store, _ = _store(tmp_path)
    store.write(_ident(), {"refresh_token": CANARY}, generation=1, expected_version=None)
    with pytest.raises(CredentialSlotError):
        store.read(_ident(connection_ref="c2"), generation=1)


def test_stale_envelope_replay_across_versions_is_rejected(tmp_path):
    """An authentic v1 envelope cannot be decrypted once the fence moved to v2."""
    store, path = _store(tmp_path)
    store.write(_ident(), {"refresh_token": "v1-secret"}, generation=1, expected_version=None)
    old_envelope = _envelope(path, _ident())
    store.write(_ident(), {"refresh_token": "v2-secret"}, generation=1, expected_version=1)
    # roll the ciphertext back to v1 while the row's version fence stays at 2
    _set_envelope(path, _ident(), old_envelope)
    with pytest.raises(CredentialSlotError):  # AAD binds version -> GCM auth fails
        store.read(_ident(), generation=1)


def test_cross_identity_envelope_replay_is_rejected(tmp_path):
    """A valid envelope from slot A cannot be decrypted inside slot B's row."""
    store, path = _store(tmp_path)
    a = _ident()
    b = _ident(tenant_id="t2")
    store.write(a, {"refresh_token": "A-secret"}, generation=1, expected_version=None)
    store.write(b, {"refresh_token": "B-secret"}, generation=1, expected_version=None)
    _set_envelope(path, b, _envelope(path, a))  # graft A's ciphertext into B
    with pytest.raises(CredentialSlotError):  # AAD binds identity -> GCM auth fails
        store.read(b, generation=1)


class _IsolationMachine(RuleBasedStateMachine):
    """Two independent slots; mutating one must never perturb the other."""
    _KEYS = ("A", "B")

    def __init__(self):
        super().__init__()
        import tempfile
        self.store = SQLiteCredentialSlotStore(tempfile.mkdtemp() + "/iso.db", TestKeyProvider())
        self.ident = {"A": _ident(), "B": _ident(tenant_id="t2", owner_id="o2")}
        self.model = {k: {"exists": False, "tomb": False, "gen": 1, "ver": 0, "secret": None}
                      for k in self._KEYS}

    @rule(k=st.sampled_from(_KEYS), val=st.text(min_size=1, max_size=24))
    def create(self, k, val):
        st_ = self.model[k]
        if st_["exists"] and not st_["tomb"]:
            with pytest.raises(CredentialSlotError):
                self.store.write(self.ident[k], {"refresh_token": val},
                                 generation=st_["gen"], expected_version=None)
            return
        self.store.write(self.ident[k], {"refresh_token": val},
                         generation=st_["gen"], expected_version=None)
        st_.update(exists=True, tomb=False, ver=1, secret=val)

    @rule(k=st.sampled_from(_KEYS), val=st.text(min_size=1, max_size=24))
    def rotate(self, k, val):
        st_ = self.model[k]
        if not st_["exists"] or st_["tomb"]:
            return
        r = self.store.write(self.ident[k], {"refresh_token": val},
                             generation=st_["gen"], expected_version=st_["ver"])
        st_.update(ver=r.version, secret=val)

    @rule(k=st.sampled_from(_KEYS))
    def revoke(self, k):
        st_ = self.model[k]
        if not st_["exists"] or st_["tomb"]:
            return
        out = self.store.revoke(self.ident[k], generation=st_["gen"])
        st_.update(gen=out.generation, tomb=True, exists=False)

    @invariant()
    def each_slot_reads_its_own_secret(self):
        for k in self._KEYS:
            st_ = self.model[k]
            if st_["exists"] and not st_["tomb"]:
                got = self.store.read(self.ident[k], generation=st_["gen"])
                assert got.secret == {"refresh_token": st_["secret"]}
                assert got.version == st_["ver"]


_IsolationMachine.TestCase.settings = settings(max_examples=25, deadline=None, stateful_step_count=14)
TestIsolationMachine = _IsolationMachine.TestCase
