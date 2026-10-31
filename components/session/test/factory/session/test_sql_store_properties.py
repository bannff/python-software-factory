"""Stateful properties for SQL-backed sessions and steering."""
from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.models import SessionRecord, SteerMessage, SteerState
from factory.storage.interface import StorageRuntime


class SessionSQLMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.temp = TemporaryDirectory()
        sql = StorageRuntime().get_sql_store(
            "sqlite", db_path=f"{self.temp.name}/sessions.db",
        )
        self.store = SQLSessionStore(sql)
        now = datetime.now(timezone.utc)
        self.record = self.store.create(SessionRecord(
            tenant_id="tenant:local", owner_id="svc:local",
            session_id="session_1", thread_id="thread_1", title="Session",
            agent_id="companion-x-default", model="openrouter",
            created_at=now, updated_at=now, revision=1,
        ))
        self.steers: dict[str, SteerMessage] = {}

    def teardown(self) -> None:
        sql = self.store._sql
        close = getattr(sql, "close", None)
        if close is not None:
            close()
        self.temp.cleanup()

    @rule(title=st.text(min_size=1, max_size=40))
    def rename_with_current_revision(self, title: str) -> None:
        updated = self.store.rename(
            "tenant:local", "svc:local", "session_1",
            title, self.record.revision,
        )
        assert updated is not None
        self.record = updated

    @rule(title=st.text(min_size=1, max_size=40))
    def stale_revision_never_mutates(self, title: str) -> None:
        stale = max(0, self.record.revision - 1)
        assert self.store.rename(
            "tenant:local", "svc:local", "session_1", title, stale,
        ) is None

    @rule(archived=st.booleans())
    def archive_is_revision_fenced(self, archived: bool) -> None:
        updated = self.store.set_archived(
            "tenant:local", "svc:local", "session_1",
            archived, self.record.revision,
        )
        assert updated is not None
        self.record = updated

    @rule(pinned=st.booleans())
    def pin_is_revision_fenced(self, pinned: bool) -> None:
        updated = self.store.set_pinned(
            "tenant:local", "svc:local", "session_1",
            pinned, self.record.revision,
        )
        if self.record.archived_at is not None:
            assert updated is None
        else:
            assert updated is not None
            self.record = updated

    @rule(tags=st.lists(st.sampled_from(["urgent", "review", "blocked"]),
                        unique=True, max_size=3))
    def tags_are_revision_fenced(self, tags: list[str]) -> None:
        updated = self.store.set_tags(
            "tenant:local", "svc:local", "session_1", tuple(tags), self.record.revision,
        )
        if self.record.archived_at is not None:
            assert updated is None
        else:
            assert updated is not None
            self.record = updated

    @rule(send_id=st.from_regex(r"send_[A-Za-z0-9]{1,8}", fullmatch=True))
    def append_is_exactly_once(self, send_id: str) -> None:
        now = datetime.now(timezone.utc)
        candidate = SteerMessage(
            tenant_id="tenant:local", owner_id="svc:local",
            session_id="session_1", delivery_id=uuid4().hex,
            send_id=send_id, content="guidance", state=SteerState.WRITTEN,
            created_at=now, revision=1,
        )
        if self.record.archived_at is not None:
            with pytest.raises(ValueError, match="session not found"):
                self.store.append(candidate)
            return
        stored = self.store.append(candidate)
        if send_id in self.steers:
            assert stored.delivery_id == self.steers[send_id].delivery_id
        else:
            self.steers[send_id] = stored

    @invariant()
    def owner_scope_and_visibility_hold(self) -> None:
        assert self.store.get("tenant:local", "other", "session_1") is None
        assert self.store.get(
            "tenant:local", "svc:local", "session_1",
        ) == self.record
        visible = self.store.list("tenant:local", "svc:local")
        assert bool(visible) is (self.record.archived_at is None)


TestSessionSQLMachine = SessionSQLMachine.TestCase
