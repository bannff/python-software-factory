"""Row 9 (feature-map) — pinned messages: pin a message, session-scoped
pins panel. Proves the full stack: SQL store CAS+restart persistence,
lifecycle delegation, and the real typed MCP tool.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.session.mcp import pinned_messages as mcp
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.models import SessionRecord
from factory.session.runtime.runtime import SessionRuntime
from factory.storage.interface import StorageRuntime

NOW = datetime.now(timezone.utc)
TENANT = "tenant:local"
OWNER = "svc:local"


def _adapter(tmp_path: Path) -> SQLSessionStore:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "sessions.db"))
    return SQLSessionStore(sql)


def _session(session_id: str = "session_1") -> SessionRecord:
    return SessionRecord(
        tenant_id=TENANT, owner_id=OWNER, session_id=session_id,
        thread_id=f"thread_{session_id}", title="Session",
        agent_id="companion-x-default", model="openrouter",
        created_at=NOW, updated_at=NOW, revision=1,
    )


def test_sql_store_pins_persist_across_restart_and_are_cas_fenced(tmp_path: Path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())

    pinned = store.set_pinned_messages(TENANT, OWNER, "session_1", ("msg-1", "msg-2"), 1)
    assert pinned is not None and pinned.pinned_message_ids == ("msg-1", "msg-2")

    # Stale-revision rejection.
    assert store.set_pinned_messages(TENANT, OWNER, "session_1", ("msg-3",), 1) is None
    # Owner isolation.
    assert store.set_pinned_messages(TENANT, "other-owner", "session_1", ("msg-3",), 2) is None

    restarted = _adapter(tmp_path)
    reread = restarted.get(TENANT, OWNER, "session_1")
    assert reread is not None and reread.pinned_message_ids == ("msg-1", "msg-2")


def test_sql_store_pin_ids_survive_special_characters(tmp_path: Path) -> None:
    """Message ids are opaque strings with no format guarantee — a comma
    or other separator-like character must round-trip exactly, unlike
    the comma-joined ``tags`` column."""
    store = _adapter(tmp_path)
    store.create(_session())
    tricky = ("msg,with,commas", "msg\"with\"quotes", "msg[with]brackets")
    store.set_pinned_messages(TENANT, OWNER, "session_1", tricky, 1)
    assert _adapter(tmp_path).get(TENANT, OWNER, "session_1").pinned_message_ids == tricky


def test_lifecycle_delegates_to_the_store(tmp_path: Path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    lifecycle = SessionLifecycle(store)
    result = lifecycle.set_pinned_messages(TENANT, OWNER, "session_1", ("m1",), 1)
    assert result.pinned_message_ids == ("m1",)


def test_pinned_messages_mcp_tool_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    runtime = SessionRuntime(SessionLifecycle(store))
    catalog = ToolCatalog("session")
    mcp.register(catalog, lambda: runtime)
    tools = {tool.name: tool for tool in __import__("asyncio").run(catalog.list_tools())}

    def _env():
        return {"tenant_id": TENANT, "principal_id": OWNER}

    saved = tools["session_set_pinned_messages"].fn(
        session_id="session_1", pinned_message_ids=("m1", "m2"),
        expected_revision=1, envelope=_env(),
    )
    assert saved.ok and saved.data.session.pinned_message_ids == ("m1", "m2")
    assert tools["session_set_pinned_messages"].fn._mcp_category == "operational"


def test_ingress_rejects_duplicate_and_blank_pins() -> None:
    from factory.session.mcp.pinned_messages_contracts import SetPinnedMessagesInput
    with pytest.raises(ValidationError):
        SetPinnedMessagesInput(session_id="s1", pinned_message_ids=("a", "a"), expected_revision=1)
    with pytest.raises(ValidationError):
        SetPinnedMessagesInput(session_id="s1", pinned_message_ids=("  ",), expected_revision=1)


def test_ingress_rejects_more_than_thirty_two_pins() -> None:
    from factory.session.mcp.pinned_messages_contracts import SetPinnedMessagesInput
    with pytest.raises(ValidationError):
        SetPinnedMessagesInput(
            session_id="s1", pinned_message_ids=tuple(f"m{i}" for i in range(33)),
            expected_revision=1,
        )
