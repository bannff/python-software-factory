"""Hypothesis stateful + concurrency tests for the migration receipt store.

The state machine drives ``record_receipt`` against a shadow model and
asserts the exact idempotent status (committed/replayed/superseded/conflict),
owner-scoped list parity, and no-overwrite of settled receipts. A separate
thread race proves the SQLite PRIMARY-KEY CAS admits exactly one committer.
"""
from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.receipt_models import (
    CommitStatus, ImportOutcome, ImportReceipt,
)
from factory.storage.interface import StorageRuntime

_T = "tenant-1"
_A = "kirocrew-v1"
_FP = "sha256:" + "f" * 32
_D1 = "sha256:" + "1" * 32
_D2 = "sha256:" + "2" * 32

_owners = st.sampled_from(["owner-1", "owner-2"])
_kinds = st.sampled_from(["memory", "lessons"])
_rids = st.sampled_from(["rec-1", "rec-2"])
_digests = st.sampled_from([_D1, _D2])
_outcomes = st.sampled_from([ImportOutcome.IMPORTED, ImportOutcome.SKIPPED, ImportOutcome.FAILED])


def _r(owner: str, kind: str, rid: str, digest: str, outcome: ImportOutcome) -> ImportReceipt:
    return ImportReceipt(tenant_id=_T, owner_id=owner, adapter=_A, source_fingerprint=_FP,
                         kind=kind, source_record_id=rid, target_digest=digest, outcome=outcome)


def test_concurrent_divergent_writes_admit_one_committer() -> None:
    """Two connections, one identity, different digests -> one COMMITTED, one CONFLICT."""
    with tempfile.TemporaryDirectory() as d:
        db = str(Path(d) / "race.db")
        store_a = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
        store_b = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))

        def write(pair):
            store, digest = pair
            return store.record_receipt(
                _r("owner-1", "memory", "rec-1", digest, ImportOutcome.IMPORTED)).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(write, [(store_a, _D1), (store_b, _D2)]))

        assert statuses.count(CommitStatus.COMMITTED) == 1
        assert CommitStatus.CONFLICT in statuses
        persisted = store_a.find_receipt(_T, "owner-1", _A, _FP, "memory", "rec-1")
        assert persisted.target_digest in {_D1, _D2}


class ReceiptStoreMachine(RuleBasedStateMachine):
    @initialize()
    def setup(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="receipt-sm-"))
        self.store = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=str(self._dir / "sm.db")))
        # (owner, kind, rid) -> {"digest", "outcome", "rev", "settled"}
        self.model: dict[tuple[str, str, str], dict] = {}

    @rule(owner=_owners, kind=_kinds, rid=_rids, digest=_digests, outcome=_outcomes)
    def record(self, owner, kind, rid, digest, outcome) -> None:
        key = (owner, kind, rid)
        prior = self.model.get(key)
        commit = self.store.record_receipt(_r(owner, kind, rid, digest, outcome))
        if prior is None:
            assert commit.status is CommitStatus.COMMITTED
            self.model[key] = {"digest": digest, "outcome": outcome.value,
                               "rev": 1, "settled": outcome.is_settled}
        elif not prior["settled"]:
            assert commit.status is CommitStatus.SUPERSEDED
            self.model[key] = {"digest": digest, "outcome": outcome.value,
                               "rev": prior["rev"] + 1, "settled": outcome.is_settled}
        elif digest == prior["digest"]:
            assert commit.status is CommitStatus.REPLAYED  # settled, no change
        else:
            assert commit.status is CommitStatus.CONFLICT   # settled, no overwrite

    @invariant()
    def list_parity_and_isolation(self) -> None:
        for owner in ("owner-1", "owner-2"):
            rows = {(r.kind, r.source_record_id): (r.target_digest, r.outcome.value, r.revision)
                    for r in self.store.list_receipts(_T, owner, _A, _FP)}
            expected = {(k, rid): (v["digest"], v["outcome"], v["rev"])
                        for (own, k, rid), v in self.model.items() if own == owner}
            assert rows == expected

    def teardown(self) -> None:
        pass


TestReceiptStoreStateful = ReceiptStoreMachine.TestCase
TestReceiptStoreStateful.settings = settings(max_examples=60, deadline=None)
