"""SQLite adapter for owner-scoped chat preferences."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from threading import Lock

from ..chat_preferences import UNSET, ChatPreferences, StaleChatPreferences

_SCHEMA = """CREATE TABLE IF NOT EXISTS ui_chat_preferences (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
 plain_diffs INTEGER NOT NULL, hidden_models TEXT NOT NULL,
 theme TEXT NOT NULL DEFAULT 'system',
 terminal_font_size INTEGER NOT NULL DEFAULT 11,
 terminal_shell TEXT,
 terminal_completion_enabled INTEGER NOT NULL DEFAULT 1,
 density TEXT NOT NULL DEFAULT 'comfortable',
 language TEXT NOT NULL DEFAULT 'en',
 shortcuts TEXT NOT NULL DEFAULT '{}',
 default_memory_mode TEXT NOT NULL DEFAULT 'persistent',
 collapse_message_input INTEGER NOT NULL DEFAULT 0,
 pin_latest_prompt INTEGER NOT NULL DEFAULT 0,
 revision INTEGER NOT NULL,
 PRIMARY KEY (tenant_id, owner_id)
)"""
_COLUMNS = (
    "plain_diffs", "hidden_models", "theme", "terminal_font_size",
    "terminal_shell", "terminal_completion_enabled", "density", "language",
    "shortcuts", "default_memory_mode", "collapse_message_input",
    "pin_latest_prompt", "revision",
)
_ADDITIVE = {
    "theme": "TEXT NOT NULL DEFAULT 'system'",
    "terminal_font_size": "INTEGER NOT NULL DEFAULT 11",
    "terminal_shell": "TEXT",
    "terminal_completion_enabled": "INTEGER NOT NULL DEFAULT 1",
    "density": "TEXT NOT NULL DEFAULT 'comfortable'",
    "language": "TEXT NOT NULL DEFAULT 'en'",
    "shortcuts": "TEXT NOT NULL DEFAULT '{}'",
    "default_memory_mode": "TEXT NOT NULL DEFAULT 'persistent'",
    "collapse_message_input": "INTEGER NOT NULL DEFAULT 0",
    "pin_latest_prompt": "INTEGER NOT NULL DEFAULT 0",
}


class SqliteChatPreferenceStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(_SCHEMA)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(ui_chat_preferences)")}
            for name, ddl in _ADDITIVE.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE ui_chat_preferences ADD COLUMN {name} {ddl}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @staticmethod
    def _model(row: tuple[object, ...] | None) -> ChatPreferences:
        if row is None:
            return ChatPreferences()
        hidden = json.loads(str(row[1]))
        return ChatPreferences(
            plain_diffs=bool(row[0]), hidden_models=tuple(hidden),
            theme=str(row[2]), terminal_font_size=int(row[3]),
            terminal_shell=(str(row[4]) if row[4] is not None else None),
            terminal_completion_enabled=bool(row[5]),
            density=str(row[6]), language=str(row[7]),
            shortcuts=dict(json.loads(str(row[8]))),
            default_memory_mode=str(row[9]),  # type: ignore[arg-type]
            collapse_message_input=bool(row[10]),
            pin_latest_prompt=bool(row[11]),
            revision=int(row[12]),
        )

    def _select(self, connection: sqlite3.Connection, tenant_id: str, owner_id: str) -> ChatPreferences:
        row = connection.execute(
            f"SELECT {','.join(_COLUMNS)} FROM ui_chat_preferences WHERE tenant_id=? AND owner_id=?",
            (tenant_id, owner_id),
        ).fetchone()
        return self._model(row), row is None  # type: ignore[return-value]

    def get(self, tenant_id: str, owner_id: str) -> ChatPreferences:
        with self._connect() as connection:
            current, _ = self._select(connection, tenant_id, owner_id)
        return current

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, plain_diffs: bool, hidden_models: tuple[str, ...],
        default_memory_mode: str | object = UNSET,
        collapse_message_input: bool | object = UNSET,
        pin_latest_prompt: bool | object = UNSET,
    ) -> ChatPreferences:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current, inserting = self._select(connection, tenant_id, owner_id)
            if current.revision != expected_revision:
                raise StaleChatPreferences("stale chat preferences")
            desired = ChatPreferences(
                plain_diffs=plain_diffs, hidden_models=hidden_models,
                theme=current.theme, terminal_font_size=current.terminal_font_size,
                terminal_shell=current.terminal_shell,
                terminal_completion_enabled=current.terminal_completion_enabled,
                density=current.density, language=current.language,
                shortcuts=current.shortcuts,
                default_memory_mode=(
                    current.default_memory_mode if default_memory_mode is UNSET
                    else default_memory_mode),  # type: ignore[arg-type]
                collapse_message_input=(
                    current.collapse_message_input if collapse_message_input is UNSET
                    else collapse_message_input),  # type: ignore[arg-type]
                pin_latest_prompt=(
                    current.pin_latest_prompt if pin_latest_prompt is UNSET
                    else pin_latest_prompt),  # type: ignore[arg-type]
                revision=current.revision + 1,
            )
            self._write(connection, tenant_id, owner_id, desired, inserting)
        return desired

    def update_display(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, theme: str, terminal_font_size: int,
        terminal_shell: str | None | object = UNSET,
        terminal_completion_enabled: bool | object = UNSET,
        density: str | object = UNSET, language: str | object = UNSET,
        shortcuts: dict[str, str] | object = UNSET,
    ) -> ChatPreferences:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current, inserting = self._select(connection, tenant_id, owner_id)
            if current.revision != expected_revision:
                raise StaleChatPreferences("stale chat preferences")
            desired = ChatPreferences(
                plain_diffs=current.plain_diffs, hidden_models=current.hidden_models,
                theme=theme, terminal_font_size=terminal_font_size,
                terminal_shell=(
                    current.terminal_shell if terminal_shell is UNSET
                    else terminal_shell),  # type: ignore[arg-type]
                terminal_completion_enabled=(
                    current.terminal_completion_enabled
                    if terminal_completion_enabled is UNSET
                    else terminal_completion_enabled),  # type: ignore[arg-type]
                density=current.density if density is UNSET else density,  # type: ignore[arg-type]
                language=current.language if language is UNSET else language,  # type: ignore[arg-type]
                shortcuts=current.shortcuts if shortcuts is UNSET else shortcuts,  # type: ignore[arg-type]
                default_memory_mode=current.default_memory_mode,
                collapse_message_input=current.collapse_message_input,
                pin_latest_prompt=current.pin_latest_prompt,
                revision=current.revision + 1,
            )
            self._write(connection, tenant_id, owner_id, desired, inserting)
        return desired

    @staticmethod
    def _write(
        connection: sqlite3.Connection, tenant: str, owner: str,
        value: ChatPreferences, inserting: bool,
    ) -> None:
        material = (
            int(value.plain_diffs), json.dumps(list(value.hidden_models)),
            value.theme, value.terminal_font_size, value.terminal_shell,
            int(value.terminal_completion_enabled), value.density, value.language,
            json.dumps(value.shortcuts, sort_keys=True), value.default_memory_mode,
            int(value.collapse_message_input), int(value.pin_latest_prompt), value.revision,
        )
        if inserting:
            connection.execute(
                f"INSERT INTO ui_chat_preferences (tenant_id,owner_id,{','.join(_COLUMNS)}) "
                f"VALUES (?,?,{','.join('?' * len(_COLUMNS))})", (tenant, owner, *material),
            )
        else:
            assignments = ",".join(f"{name}=?" for name in _COLUMNS)
            changed = connection.execute(
                f"UPDATE ui_chat_preferences SET {assignments} "
                "WHERE tenant_id=? AND owner_id=? AND revision=?",
                (*material, tenant, owner, value.revision - 1),
            ).rowcount
            if changed != 1:
                raise StaleChatPreferences("stale chat preferences")


__all__ = ["SqliteChatPreferenceStore"]
