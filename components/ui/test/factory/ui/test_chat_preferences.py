"""Durable owner-scoped Chat preference contracts."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3
import tempfile

from hypothesis import given, settings, strategies as st
import pytest
from pydantic import ValidationError

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.ui.mcp import chat_preferences as mcp
from factory.ui.runtime.adapters.chat_preferences_sqlite import SqliteChatPreferenceStore
from factory.ui.runtime.chat_preferences import StaleChatPreferences


def test_sqlite_chat_preferences_restart_owner_and_cas(tmp_path: Path) -> None:
    path = tmp_path / "preferences.db"
    store = SqliteChatPreferenceStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    saved = store.update(
        "tenant", "owner", 0, plain_diffs=True,
        hidden_models=("openrouter/a",),
    )
    assert saved.revision == 1
    displayed = store.update_display(
        "tenant", "owner", 1, theme="light", terminal_font_size=16,
    )
    assert displayed.plain_diffs and displayed.hidden_models == ("openrouter/a",)
    assert displayed.theme == "light" and displayed.terminal_font_size == 16
    assert SqliteChatPreferenceStore(path).get("tenant", "owner") == displayed
    assert store.get("tenant", "other").revision == 0
    with pytest.raises(StaleChatPreferences):
        store.update("tenant", "owner", 0, plain_diffs=False, hidden_models=())


@settings(deadline=None)
@given(st.lists(st.tuples(st.booleans(), st.sets(
    st.from_regex(r"[a-z][a-z0-9/-]{0,20}", fullmatch=True), max_size=4,
)), min_size=1, max_size=12))
def test_preference_transitions_round_trip(
    changes: list[tuple[bool, set[str]]],
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "preferences.db"
        store = SqliteChatPreferenceStore(path)
        revision = 0
        for plain, hidden in changes:
            expected = tuple(sorted(hidden))
            row = store.update(
                "tenant", "owner", revision,
                plain_diffs=plain, hidden_models=expected,
            )
            revision += 1
            assert row.revision == revision
            assert SqliteChatPreferenceStore(path).get("tenant", "owner") == row


def test_chat_preferences_mcp_is_typed_owner_scoped_and_conflict_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SqliteChatPreferenceStore(tmp_path / "preferences.db")
    catalog = ToolCatalog("ui")
    mcp.register(catalog, store)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    monkeypatch.setattr(
        mcp, "get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    initial = tools["ui_get_chat_preferences"].fn()
    assert initial.ok and initial.data.revision == 0
    saved = tools["ui_update_chat_preferences"].fn(
        plain_diffs=True, hidden_models=["openrouter/a"], expected_revision=0,
    )
    assert saved.ok and saved.data.hidden_models == ("openrouter/a",)
    conflict = tools["ui_update_chat_preferences"].fn(
        plain_diffs=False, hidden_models=[], expected_revision=0,
    )
    assert not conflict.ok and conflict.error == "chat_preferences_conflict"
    monkeypatch.setattr(mcp, "get_envelope", lambda: None)
    assert not tools["ui_get_chat_preferences"].fn().ok
    assert tools["ui_get_chat_preferences"].fn._mcp_category == "deterministic"
    assert tools["ui_update_chat_preferences"].fn._mcp_category == "operational"


def test_chat_preferences_ingress_rejects_unknown_duplicate_and_blank() -> None:
    with pytest.raises(ValidationError):
        mcp.UpdateChatPreferencesInput(
            plain_diffs=True, hidden_models=[], expected_revision=0, extra=True,
        )
    with pytest.raises(ValidationError):
        mcp.UpdateChatPreferencesInput(
            plain_diffs=True, hidden_models=["a", "a"], expected_revision=0,
        )
    with pytest.raises(ValidationError):
        mcp.UpdateChatPreferencesInput(
            plain_diffs=True, hidden_models=[" "], expected_revision=0,
        )


def test_default_memory_mode_round_trips_and_rejects_unknown_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 3 (feature-map): the owner's chosen default mode for new
    dashboard-created chats must persist, defaulting to persistent, and
    the real MCP boundary must reject anything outside the three values."""
    store = SqliteChatPreferenceStore(tmp_path / "preferences.db")
    catalog = ToolCatalog("ui")
    mcp.register(catalog, store)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    monkeypatch.setattr(
        mcp, "get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    initial = tools["ui_get_chat_preferences"].fn()
    assert initial.ok and initial.data.default_memory_mode == "persistent"
    saved = tools["ui_update_chat_preferences"].fn(
        plain_diffs=False, hidden_models=[], expected_revision=0,
        default_memory_mode="incognito",
    )
    assert saved.ok and saved.data.default_memory_mode == "incognito"
    reread = tools["ui_get_chat_preferences"].fn()
    assert reread.ok and reread.data.default_memory_mode == "incognito"
    with pytest.raises(ValidationError):
        mcp.UpdateChatPreferencesInput(
            plain_diffs=False, hidden_models=[], expected_revision=1,
            default_memory_mode="bogus",
        )


def test_update_display_without_terminal_args_does_not_reset_existing_shell(
    tmp_path: Path,
) -> None:
    """A theme/font-only save must not silently clear a previously saved shell.

    update_display's terminal_shell/terminal_completion_enabled parameters
    default to (None, True) at the signature level so existing theme/font-only
    callers keep compiling, but the STORE itself must still preserve whatever
    was already saved when the caller omits them -- otherwise a Display-panel
    theme change would silently wipe an unrelated Settings->Terminal shell
    choice. This is the correctness property, not just signature compatibility.
    """
    path = tmp_path / "preferences.db"
    store = SqliteChatPreferenceStore(path)
    with_shell = store.update_display(
        "tenant", "owner", 0, theme="dark", terminal_font_size=12,
        terminal_shell="/bin/zsh", terminal_completion_enabled=False,
    )
    assert with_shell.terminal_shell == "/bin/zsh"
    assert with_shell.terminal_completion_enabled is False

    theme_only = store.update_display(
        "tenant", "owner", with_shell.revision, theme="light", terminal_font_size=14,
    )
    assert theme_only.theme == "light" and theme_only.terminal_font_size == 14
    assert theme_only.terminal_shell == "/bin/zsh", (
        "theme-only save must preserve the previously saved shell"
    )
    assert theme_only.terminal_completion_enabled is False, (
        "theme-only save must preserve the previously saved completion flag"
    )


def test_row_12_collapse_message_input_round_trips_and_survives_a_display_only_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 12 (feature-map): "Collapse the message input" persists like
    every other Chat preference here, and — since it lives on the SAME
    record as default_memory_mode — a plain Display-panel update must
    not silently reset it back to its off-by-default value."""
    store = SqliteChatPreferenceStore(tmp_path / "preferences.db")
    catalog = ToolCatalog("ui")
    mcp.register(catalog, store)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    monkeypatch.setattr(
        mcp, "get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    initial = tools["ui_get_chat_preferences"].fn()
    assert initial.ok and initial.data.collapse_message_input is False

    saved = tools["ui_update_chat_preferences"].fn(
        plain_diffs=False, hidden_models=[], expected_revision=0,
        collapse_message_input=True,
    )
    assert saved.ok and saved.data.collapse_message_input is True
    reread = tools["ui_get_chat_preferences"].fn()
    assert reread.ok and reread.data.collapse_message_input is True

    # A later plain-Chat update omitting the field must preserve it.
    unrelated = tools["ui_update_chat_preferences"].fn(
        plain_diffs=True, hidden_models=[], expected_revision=reread.data.revision,
    )
    assert unrelated.ok and unrelated.data.collapse_message_input is True, (
        "omitting collapse_message_input on an unrelated update must not reset it"
    )


def test_in_memory_store_update_display_does_not_reset_default_memory_mode(tmp_path: Path) -> None:
    """Real pre-existing bug found while adding row 12: the IN-MEMORY
    store's own update_display omitted default_memory_mode/
    collapse_message_input from its ChatPreferences(...) reconstruction,
    silently resetting BOTH back to their class defaults on every plain
    display update — the SQLite adapter never had this bug. Pinned here
    so it cannot silently return."""
    from factory.ui.runtime.chat_preferences import InMemoryChatPreferenceStore

    store = InMemoryChatPreferenceStore()
    store.update(
        "tenant", "owner", 0, plain_diffs=False, hidden_models=(),
        default_memory_mode="incognito",
    )
    updated = store.update_display(
        "tenant", "owner", 1, theme="dark", terminal_font_size=14,
    )
    assert updated.default_memory_mode == "incognito", (
        "a display-only update must not reset default_memory_mode"
    )
    assert updated.collapse_message_input is False


def test_row_10_pin_latest_prompt_round_trips_and_survives_a_display_only_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 10 (feature-map): "Pin the latest turn" persists like every
    other Chat preference and — living on the SAME record as
    collapse_message_input/default_memory_mode — must not be reset by an
    unrelated plain-Chat or Display update that omits it."""
    store = SqliteChatPreferenceStore(tmp_path / "preferences.db")
    catalog = ToolCatalog("ui")
    mcp.register(catalog, store)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    monkeypatch.setattr(
        mcp, "get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    initial = tools["ui_get_chat_preferences"].fn()
    assert initial.ok and initial.data.pin_latest_prompt is False

    saved = tools["ui_update_chat_preferences"].fn(
        plain_diffs=False, hidden_models=[], expected_revision=0,
        pin_latest_prompt=True,
    )
    assert saved.ok and saved.data.pin_latest_prompt is True
    reread = tools["ui_get_chat_preferences"].fn()
    assert reread.ok and reread.data.pin_latest_prompt is True

    # A later unrelated update (toggling a DIFFERENT field) must preserve it.
    unrelated = tools["ui_update_chat_preferences"].fn(
        plain_diffs=True, hidden_models=[], expected_revision=reread.data.revision,
        collapse_message_input=True,
    )
    assert unrelated.ok and unrelated.data.pin_latest_prompt is True, (
        "omitting pin_latest_prompt on an unrelated update must not reset it"
    )
    assert unrelated.data.collapse_message_input is True


def test_in_memory_store_update_display_preserves_pin_latest_prompt(tmp_path: Path) -> None:
    """Row 10: the in-memory store's update_display must carry
    pin_latest_prompt forward, not silently reset it (the same class of
    bug row 12 fixed for collapse_message_input)."""
    from factory.ui.runtime.chat_preferences import InMemoryChatPreferenceStore

    store = InMemoryChatPreferenceStore()
    store.update(
        "tenant", "owner", 0, plain_diffs=False, hidden_models=(),
        pin_latest_prompt=True,
    )
    updated = store.update_display(
        "tenant", "owner", 1, theme="dark", terminal_font_size=14,
    )
    assert updated.pin_latest_prompt is True, (
        "a display-only update must not reset pin_latest_prompt"
    )
