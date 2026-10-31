"""CredentialBroker lifecycle: single-flight, one 401 retry, revoke eviction.

Uses an in-memory SecretStorePort so broker logic is exercised without the MCP
transport/pool. Tokens are never returned by the public surface — the broker
only yields sanitized EgressResult objects.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Mapping

from factory.auth.runtime.credential_broker import CredentialBroker
from factory.auth.runtime.adapters.fake_providers import FakeProvider
from factory.auth.runtime.egress_models import SlotCoordinate
from factory.auth.runtime.egress_ports import SecretRead, SlotOutcome
from factory.auth.runtime.egress_registry import resolve_route

CANARY = "refresh-CANARY-9988776655443322"


class MemStore:
    """Minimal in-memory SecretStorePort mirroring generation/version semantics."""
    def __init__(self):
        self._rows: dict[tuple, dict] = {}

    def _k(self, c): return (c.tenant_id, c.owner_id, c.provider_id, c.connection_ref, c.slot_kind)

    def write(self, coord, secret, *, generation, expected_version):
        row = self._rows.get(self._k(coord))
        if expected_version is None:
            if row and not row["tomb"]:
                return None
            self._rows[self._k(coord)] = {"gen": generation, "ver": 1, "secret": dict(secret), "tomb": False}
            return SlotOutcome(generation, 1)
        if not row or row["tomb"] or row["gen"] != generation or row["ver"] != expected_version:
            return None
        row.update(ver=expected_version + 1, secret=dict(secret))
        return SlotOutcome(generation, row["ver"])

    def read(self, coord, *, generation):
        row = self._rows.get(self._k(coord))
        if not row or row["tomb"] or row["gen"] != generation:
            return None
        return SecretRead(secret=dict(row["secret"]), generation=row["gen"], version=row["ver"])

    def revoke(self, coord, *, generation):
        row = self._rows.get(self._k(coord))
        if not row or row["tomb"] or row["gen"] != generation:
            return None
        row.update(tomb=True, gen=generation + 1)
        return SlotOutcome(generation + 1, row["ver"])


def _coord():
    return SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token")


def _route():
    return resolve_route("microsoft", "send_mail")


def test_enroll_then_egress_returns_sanitized_result_only():
    provider = FakeProvider()
    broker = CredentialBroker(MemStore(), {"microsoft": provider})
    assert broker.enroll(_coord(), {"refresh_token": CANARY})
    result = broker.egress(_coord(), _route(), {"subject": "hi", "body": "b", "to": "x@y.z"})
    assert result.status == "ok"
    blob = result.model_dump_json()
    assert CANARY not in blob and "fat_" not in blob  # no secret, no access token


def test_adobe_client_credentials_path():
    broker = CredentialBroker(MemStore(), {"adobe": FakeProvider()})
    coord = SlotCoordinate("t1", "o1", "adobe", "c9", "client_secret")
    assert broker.enroll(coord, {"client_secret": "sekret"})
    result = broker.egress(coord, resolve_route("adobe", "indesign_datamerge"),
                           {"template_ref": "tpl", "data_ref": "csv"})
    assert result.status == "ok" and result.result["provider_id"] == "adobe"


def test_single_flight_one_acquire_under_concurrency():
    class SlowProvider(FakeProvider):
        def acquire(self, route, secret, *, force_refresh):
            time.sleep(0.05)
            return super().acquire(route, secret, force_refresh=force_refresh)

    provider = SlowProvider()
    broker = CredentialBroker(MemStore(), {"microsoft": provider})
    broker.enroll(_coord(), {"refresh_token": CANARY})
    barrier = threading.Barrier(4)

    def go():
        barrier.wait()
        broker.egress(_coord(), _route(), {"subject": "s", "body": "b", "to": "t@x.z"})

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert provider.acquire_calls == 1  # single-flight collapsed the refresh


def test_one_401_retry_then_success():
    provider = FakeProvider(unauthorized_first=True)
    broker = CredentialBroker(MemStore(), {"microsoft": provider})
    broker.enroll(_coord(), {"refresh_token": CANARY})
    result = broker.egress(_coord(), _route(), {"subject": "s", "body": "b", "to": "t@x.z"})
    assert result.status == "ok"
    assert provider.acquire_calls == 2 and provider.call_count == 2  # exactly one forced retry


def test_revoke_invalidates_cache_and_blocks_egress():
    broker = CredentialBroker(MemStore(), {"microsoft": FakeProvider()})
    broker.enroll(_coord(), {"refresh_token": CANARY})
    assert broker.egress(_coord(), _route(), {"subject": "s", "body": "b", "to": "t@x.z"}).status == "ok"
    assert broker.revoke(_coord())
    assert broker.egress(_coord(), _route(), {"subject": "s", "body": "b", "to": "t@x.z"}).status == "unauthorized"


def test_unknown_provider_denied():
    broker = CredentialBroker(MemStore(), {})
    assert broker.egress(_coord(), _route(), {"subject": "s", "body": "b", "to": "t@x.z"}).status == "denied"
