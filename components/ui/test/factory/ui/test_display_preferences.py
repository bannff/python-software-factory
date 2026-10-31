"""Typed owner-scoped Display preference MCP contracts."""
import asyncio
from pathlib import Path
import pytest
from pydantic import ValidationError
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.ui.mcp import display_preferences as mcp
from factory.ui.runtime.adapters.chat_preferences_sqlite import SqliteChatPreferenceStore

def test_display_mcp_round_trip_and_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteChatPreferenceStore(tmp_path / "prefs.db")
    catalog = ToolCatalog("ui"); mcp.register(catalog, store)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    monkeypatch.setattr(mcp, "get_envelope", lambda: {"tenant_id": "tenant", "principal_id": "owner"})
    initial = tools["ui_get_display_preferences"].fn()
    assert initial.ok and initial.data.theme == "system" and initial.data.terminal_font_size == 11
    assert initial.data.density == "comfortable" and initial.data.language == "en"
    saved = tools["ui_update_display_preferences"].fn(
        theme="dark", terminal_font_size=14, expected_revision=0,
        terminal_shell="/bin/zsh", terminal_completion_enabled=False,
        density="compact", language="de-DE", shortcuts={"command_palette": "mod+shift+p"},
    )
    assert saved.ok and saved.data.theme == "dark" and saved.data.revision == 1
    assert saved.data.shortcuts == {"command_palette": "mod+shift+p"}
    assert saved.data.density == "compact" and saved.data.language == "de-DE"
    with pytest.raises(SchemaMigrationError):
        tools["ui_update_display_preferences"].fn(
            theme="light", terminal_font_size=15, expected_revision=1,
        )
    unchanged = tools["ui_get_display_preferences"].fn()
    assert unchanged.ok and unchanged.data.terminal_shell == "/bin/zsh"
    assert unchanged.data.terminal_completion_enabled is False
    assert unchanged.data.density == "compact" and unchanged.data.language == "de-DE"
    assert unchanged.data.shortcuts == {"command_palette": "mod+shift+p"}
    conflict = tools["ui_update_display_preferences"].fn(
        theme="light", terminal_font_size=12, expected_revision=0,
        terminal_shell="/bin/zsh", terminal_completion_enabled=False,
        density="compact", language="de-DE", shortcuts={},
    )
    assert not conflict.ok and conflict.error == "display_preferences_conflict"
    assert tools["ui_get_display_preferences"].fn._mcp_category == "deterministic"
    assert tools["ui_update_display_preferences"].fn._mcp_category == "operational"

def test_display_ingress_is_strict_and_bounded() -> None:
    base = dict(terminal_shell=None, terminal_completion_enabled=True, expected_revision=0,
                density="comfortable", language="en", shortcuts={})
    with pytest.raises(ValidationError):
        mcp.UpdateDisplayPreferencesInput(theme="blue", terminal_font_size=12, **base)
    with pytest.raises(ValidationError):
        mcp.UpdateDisplayPreferencesInput(theme="dark", terminal_font_size=40, **base)
    with pytest.raises(ValidationError):
        mcp.UpdateDisplayPreferencesInput(theme="dark", terminal_font_size=12, **{**base, "density": "cozy"})
    with pytest.raises(ValidationError):
        mcp.UpdateDisplayPreferencesInput(theme="dark", terminal_font_size=12, **{**base, "language": "English!"})


def test_shortcut_overrides_are_normalized_chords_only() -> None:
    from factory.ui.runtime.chat_preferences import ChatPreferences
    ChatPreferences(shortcuts={"command_palette": "mod+shift+p", "toggle_terminal": "alt+t"})
    for bad in ({"Command Palette": "mod+k"}, {"x": "Cmd+K"}, {"x": "mod+"}, {"x": "mod+ctrl+k"}):
        with pytest.raises(ValidationError):
            ChatPreferences(shortcuts=bad)


def test_display_sqlite_migrates_pre_density_rows(tmp_path: Path) -> None:
    """Rows written before density/language existed read back with defaults."""
    import sqlite3
    path = tmp_path / "prefs.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE ui_chat_preferences (
            tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, plain_diffs INTEGER NOT NULL,
            hidden_models TEXT NOT NULL, theme TEXT NOT NULL DEFAULT 'system',
            terminal_font_size INTEGER NOT NULL DEFAULT 11, terminal_shell TEXT,
            terminal_completion_enabled INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, owner_id))""")
        connection.execute("INSERT INTO ui_chat_preferences VALUES ('t','o',0,'[]','light',13,NULL,1,3)")
    store = SqliteChatPreferenceStore(path)
    current = store.get("t", "o")
    assert (current.theme, current.terminal_font_size, current.revision) == ("light", 13, 3)
    assert current.density == "comfortable" and current.language == "en" and current.shortcuts == {}
    updated = store.update_display("t", "o", 3, theme="light", terminal_font_size=13, density="compact")
    assert updated.density == "compact" and updated.language == "en" and updated.revision == 4
    remapped = store.update_display("t", "o", 4, theme="light", terminal_font_size=13, shortcuts={"command_palette": "mod+p"})
    assert remapped.shortcuts == {"command_palette": "mod+p"} and store.get("t", "o").shortcuts == {"command_palette": "mod+p"}


def test_backend_chord_grammar_matches_shared_vectors() -> None:
    """Parity with frontends/next-dashboard/lib/shortcuts.ts (same vector file)."""
    import json
    from factory.ui.runtime.chat_preferences import ChatPreferences
    vectors = json.loads((Path(__file__).parent / "fixtures" / "shortcut_chords.json").read_text())
    for chord in vectors["accept"]:
        ChatPreferences(shortcuts={"command_palette": chord})
    for chord in vectors["reject"]:
        with pytest.raises(ValidationError):
            ChatPreferences(shortcuts={"command_palette": chord})
