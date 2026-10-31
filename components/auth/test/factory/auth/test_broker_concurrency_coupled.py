"""wd87r: coupled concurrency — one provider refresh per broker AND a single
CAS write-back winner when two brokers (two processes) rotate the same slot.

Two brokers share ONE compare-and-swap secret store. Both are forced to refresh
concurrently, and each fake provider rotates the durable secret on refresh. A
barrier makes both read version 1 before either writes back, so their CAS writes
(both expected_version=1) genuinely race. Exactly one commit wins → the store
ends at version 2, proving the fenced CAS collapses concurrent rotations to a
single winner while both brokers really performed the refresh.
"""
from __future__ import annotations

import threading

from factory.auth.runtime.credential_broker import CredentialBroker
from factory.auth.runtime.adapters.fake_providers import FakeProvider
from factory.auth.runtime.egress_models import SlotCoordinate
from factory.auth.runtime.egress_ports import SecretRead, SlotOutcome
from factory.auth.runtime.egress_registry import resolve_route

CANARY = "refresh-CANARY-coupled-abc123def456"


class SharedCasStore:
    """Minimal shared SecretStorePort with fenced CAS on (generation, version)."""
    def __init__(self):
        self._rows: dict[tuple, dict] = {}
        self._lock = threading.Lock()

    def _k(self, c):
        return (c.tenant_id, c.owner_id, c.provider_id, c.connection_ref, c.slot_kind)

    def write(self, coord, secret, *, generation, expected_version):
        with self._lock:
            row = self._rows.get(self._k(coord))
            if expected_version is None:
                if row and not row["tomb"]:
                    return None
                self._rows[self._k(coord)] = {"gen": generation, "ver": 1,
                                              "secret": dict(secret), "tomb": False}
                return SlotOutcome(generation, 1)
            if not row or row["tomb"] or row["gen"] != generation \
                    or row["ver"] != expected_version:
                return None  # stale writer loses the CAS
            row.update(ver=expected_version + 1, secret=dict(secret))
            return SlotOutcome(generation, row["ver"])

    def read(self, coord, *, generation):
        with self._lock:
            row = self._rows.get(self._k(coord))
        if not row or row["tomb"] or row["gen"] != generation:
            return None
        return SecretRead(secret=dict(row["secret"]), generation=row["gen"], version=row["ver"])

    def revoke(self, coord, *, generation):
        return None

    def version(self, coord):
        return self._rows[self._k(coord)]["ver"]


class BarrierRotateProvider(FakeProvider):
    """Rotates on the forced refresh, pausing at a shared barrier between the
    caller's secret read and the rotated write-back so the two CAS writes race."""
    def __init__(self, barrier):
        super().__init__(rotate_on_refresh=True)
        self._barrier = barrier

    def acquire(self, route, secret, *, force_refresh):
        result = super().acquire(route, secret, force_refresh=force_refresh)
        if force_refresh:
            self._barrier.wait(timeout=5)
        return result


def test_two_brokers_rotate_one_cas_winner_both_refresh():
    store = SharedCasStore()
    coord = SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token")
    route = resolve_route("microsoft", "send_mail")

    # broker A enrolls at generation 1 / version 1; broker B learns the generation
    broker_a = CredentialBroker(store, {})
    assert broker_a.enroll(coord, {"refresh_token": CANARY})

    barrier = threading.Barrier(2)
    prov_a, prov_b = BarrierRotateProvider(barrier), BarrierRotateProvider(barrier)
    broker_a = CredentialBroker(store, {"microsoft": prov_a})
    broker_b = CredentialBroker(store, {"microsoft": prov_b})
    broker_a._generations[broker_a._key(coord)] = 1
    broker_b._generations[broker_b._key(coord)] = 1

    def force(broker):
        broker._token(coord, route, broker._providers["microsoft"], force=True)

    threads = [threading.Thread(target=force, args=(b,)) for b in (broker_a, broker_b)]
    for t in threads: t.start()
    for t in threads: t.join()

    # both brokers genuinely performed a provider refresh
    assert prov_a.acquire_calls == 1 and prov_b.acquire_calls == 1
    # yet exactly one rotated write-back committed: version advanced by exactly one
    assert store.version(coord) == 2
