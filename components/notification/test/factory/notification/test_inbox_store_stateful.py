"""Hypothesis stateful + concurrency tests for the notification inbox store.

The state machine drives ``create_or_replay`` and revision-CAS marks against a
shadow model, asserting exact idempotent status, owner-scoped newest-first list
parity, and no-overwrite of a settled dedupe identity. A thread race proves the
SQLite UNIQUE(tenant, owner, dedupe_key) CAS admits exactly one creator.
"""
from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.notification.runtime.adapters.inbox_store_sql import SqlInboxStore
from factory.notification.runtime.inbox_models import (
    InboxCommitStatus, NotificationRecord, Priority,
)
from factory.notification.runtime.inbox_targets import SessionTarget
from factory.storage.interface import StorageRuntime

_T = "tenant-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_owners = st.sampled_from(["owner-1", "owner-2"])
_keys = st.sampled_from(["dk-1", "dk-2"])
_titles = st.sampled_from(["alpha", "beta"])


def _rec(owner, dk, title, seq) -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=f"ntf-{owner}-{seq}",
        kind="event", title=title, priority=Priority.DEFAULT,
        target=SessionTarget(session_id="sess-1"), dedupe_key=dk,
        created_at=_NOW + timedelta(seconds=seq))


def test_concurrent_same_key_admits_one_creator() -> None:
    with tempfile.TemporaryDirectory() as d:
        db = str(Path(d) / "race.db")
        a = SqlInboxStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
        b = SqlInboxStore(StorageRuntime().get_sql_store("sqlite", db_path=db))

        def write(pair):
            store, title, seq = pair
            return store.create_or_replay(_rec("owner-1", "dk-1", title, seq)).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(write, [(a, "alpha", 0), (b, "beta", 1)]))

        assert statuses.count(InboxCommitStatus.CREATED) == 1
        # the loser is REPLAYED (same content lost the insert) or CONFLICT (diff)
        assert InboxCommitStatus.CREATED in statuses
        assert len(a.list(_T, "owner-1", limit=10)) == 1


class InboxMachine(RuleBasedStateMachine):
    @initialize()
    def setup(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="inbox-sm-"))
        self.store = SqlInboxStore(StorageRuntime().get_sql_store(
            "sqlite", db_path=str(self._dir / "sm.db")))
        # (owner, dedupe_key) -> {"nid", "title", "created", "rev", "read"}
        self.model: dict[tuple[str, str], dict] = {}
        self._seq = 0

    @rule(owner=_owners, dk=_keys, title=_titles)
    def create(self, owner, dk, title) -> None:
        self._seq += 1
        rec = _rec(owner, dk, title, self._seq)
        commit = self.store.create_or_replay(rec)
        prior = self.model.get((owner, dk))
        if prior is None:
            assert commit.status is InboxCommitStatus.CREATED
            self.model[(owner, dk)] = {"nid": rec.notification_id, "title": title,
                                       "created": rec.created_at, "rev": 1,
                                       "read": False}
        elif prior["title"] == title:
            assert commit.status is InboxCommitStatus.REPLAYED
        else:
            assert commit.status is InboxCommitStatus.CONFLICT

    @rule(owner=_owners, dk=_keys)
    def mark_read(self, owner, dk) -> None:
        prior = self.model.get((owner, dk))
        if prior is None or prior["read"]:
            return
        rec = self.store.mark_read(_T, owner, prior["nid"],
                                   expected_revision=prior["rev"], read_at=_NOW)
        prior["rev"] = rec.revision
        prior["read"] = True

    @invariant()
    def list_parity(self) -> None:
        for owner in ("owner-1", "owner-2"):
            rows = self.store.list(_T, owner, limit=100)
            expected = sorted(
                (v for (o, _), v in self.model.items() if o == owner),
                key=lambda v: (v["created"], v["nid"]), reverse=True)
            assert [r.notification_id for r in rows] == [v["nid"] for v in expected]
            for r in rows:
                v = next(x for x in expected if x["nid"] == r.notification_id)
                assert (r.read_at is not None) == v["read"]
                assert r.revision == v["rev"]

    def teardown(self) -> None:
        pass


TestInboxStateful = InboxMachine.TestCase
TestInboxStateful.settings = settings(max_examples=60, deadline=None)
