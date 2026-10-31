"""Row 102 (feature-map) — host-side backup/restore of durable UI
preferences. Proves the full round trip through the REAL SQLite store,
not just the composition functions in isolation."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.ui.mcp import preference_backup as mcp
from factory.ui.runtime.adapters.chat_preferences_sqlite import SqliteChatPreferenceStore
from factory.ui.runtime.preference_backup import export_preferences, restore_preferences


def test_export_then_restore_round_trips_every_field(tmp_path: Path) -> None:
    path = tmp_path / "preferences.db"
    store = SqliteChatPreferenceStore(path)
    store.update(
        "tenant", "owner", 0, plain_diffs=True,
        hidden_models=("openrouter/a",), default_memory_mode="incognito",
    )
    store.update_display(
        "tenant", "owner", 1, theme="dark", terminal_font_size=16,
        terminal_shell="/bin/zsh", terminal_completion_enabled=False,
        density="compact", language="en-US", shortcuts={"open_palette": "mod+k"},
    )
    snapshot = export_preferences(store, "tenant", "owner")

    # Simulate a fresh host with nothing saved, then restore the snapshot.
    fresh_path = tmp_path / "fresh.db"
    fresh_store = SqliteChatPreferenceStore(fresh_path)
    restored = restore_preferences(fresh_store, "tenant", "owner", snapshot)

    assert restored.plain_diffs is True
    assert restored.hidden_models == ("openrouter/a",)
    assert restored.default_memory_mode == "incognito"
    assert restored.theme == "dark"
    assert restored.terminal_font_size == 16
    assert restored.terminal_shell == "/bin/zsh"
    assert restored.terminal_completion_enabled is False
    assert restored.density == "compact"
    assert restored.language == "en-US"
    assert restored.shortcuts == {"open_palette": "mod+k"}


def test_restore_overwrites_current_state_not_the_snapshots_stale_revision(tmp_path: Path) -> None:
    """A restore must CAS-fence against the store's CURRENT revision, not
    whatever revision the snapshot itself carried — otherwise every
    restore after even one intervening edit would spuriously conflict."""
    path = tmp_path / "preferences.db"
    store = SqliteChatPreferenceStore(path)
    store.update("tenant", "owner", 0, plain_diffs=True, hidden_models=())
    snapshot = export_preferences(store, "tenant", "owner")
    assert snapshot.revision == 1

    # Advance the real store further AFTER the snapshot was taken.
    store.update("tenant", "owner", 1, plain_diffs=False, hidden_models=("x",))

    restored = restore_preferences(store, "tenant", "owner", snapshot)
    assert restored.plain_diffs is True  # the snapshot's own value won
    assert restored.hidden_models == ()


def test_preference_backup_mcp_round_trips_through_real_tools(
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
    store.update("tenant", "owner", 0, plain_diffs=True, hidden_models=("m1",))
    exported = tools["ui_export_preferences"].fn()
    assert exported.ok and exported.data.plain_diffs is True

    # Change state, then restore the exported snapshot back.
    store.update("tenant", "owner", 1, plain_diffs=False, hidden_models=())
    restored = tools["ui_import_preferences"].fn(**exported.data.model_dump())
    assert restored.ok and restored.data.plain_diffs is True
    assert restored.data.hidden_models == ("m1",)

    monkeypatch.setattr(mcp, "get_envelope", lambda: None)
    assert not tools["ui_export_preferences"].fn().ok
    assert tools["ui_export_preferences"].fn._mcp_category == "deterministic"
    assert tools["ui_import_preferences"].fn._mcp_category == "operational"


def test_import_ingress_rejects_duplicate_hidden_models() -> None:
    with pytest.raises(ValidationError):
        mcp.RestorePreferencesInput(
            plain_diffs=True, hidden_models=("a", "a"), default_memory_mode="persistent",
            theme="dark", terminal_font_size=12, terminal_completion_enabled=True,
            density="comfortable", language="en", shortcuts={}, revision=0,
        )
