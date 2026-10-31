"""Owner-scoped chat presentation preferences and storage port."""
from __future__ import annotations

from threading import Lock
from typing import Any, Literal, Protocol

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ACTION = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
# Normalized chord: canonical mod→shift→alt prefixes + one key token (e.g. "mod+shift+k").
_CHORD = re.compile(r"^(?:mod\+)?(?:shift\+)?(?:alt\+)?(?:[a-z0-9`]|enter|escape|space|tab|f[1-9]|f1[0-2])$")


class ChatPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plain_diffs: bool = False
    hidden_models: tuple[str, ...] = Field(default=(), max_length=64)
    theme: Literal["system", "dark", "light"] = "system"
    terminal_font_size: int = Field(default=11, ge=10, le=18)
    terminal_shell: str | None = Field(default=None, max_length=512)
    terminal_completion_enabled: bool = True
    density: Literal["comfortable", "compact"] = "comfortable"
    language: str = Field(default="en", min_length=2, max_length=35, pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    shortcuts: dict[str, str] = Field(default_factory=dict, max_length=32)
    # Row 3 (feature-map): default mode for new dashboard-created chats.
    # Explicit per-chat choices (e.g. a Welcome-view override) always win
    # over this; app-owned and direct-API sessions never consult it.
    default_memory_mode: Literal["persistent", "incognito", "temporary"] = "persistent"
    # Row 12 (feature-map): "Collapse the message input" — off by default,
    # the owner's choice persists across sessions/reloads like every
    # other Chat preference here.
    collapse_message_input: bool = False
    # Row 10 (feature-map): "Pin the latest turn" — keep the current turn's
    # own prompt visible at the top of a long reply while it scrolls. Off
    # by default; the owner's choice persists like every other Chat pref.
    pin_latest_prompt: bool = False
    revision: int = Field(default=0, ge=0)

    @field_validator("shortcuts")
    @classmethod
    def _valid_shortcuts(cls, value: dict[str, str]) -> dict[str, str]:
        for action, chord in value.items():
            if not _ACTION.fullmatch(action) or not _CHORD.fullmatch(chord):
                raise ValueError("invalid shortcut override")
        return value

    @field_validator("hidden_models")
    @classmethod
    def _valid_models(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("hidden models must be unique")
        if any(not item.strip() or len(item) > 256 or "\x00" in item for item in value):
            raise ValueError("invalid hidden model id")
        return value

    @field_validator("terminal_shell")
    @classmethod
    def _valid_shell(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("invalid terminal shell")
        return value


class StaleChatPreferences(ValueError):
    """Raised when revision compare-and-swap fails."""


class _Unset:
    """Sentinel distinguishing an omitted argument from an explicit ``None``."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()


class ChatPreferenceStore(Protocol):
    def get(self, tenant_id: str, owner_id: str) -> ChatPreferences: ...

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, plain_diffs: bool, hidden_models: tuple[str, ...],
        default_memory_mode: str | _Unset = UNSET,
        collapse_message_input: bool | _Unset = UNSET,
        pin_latest_prompt: bool | _Unset = UNSET,
    ) -> ChatPreferences: ...

    def update_display(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, theme: str, terminal_font_size: int,
        terminal_shell: str | None | _Unset = UNSET,
        terminal_completion_enabled: bool | _Unset = UNSET,
        density: str | _Unset = UNSET,
        language: str | _Unset = UNSET,
        shortcuts: dict[str, str] | _Unset = UNSET,
    ) -> ChatPreferences: ...


class InMemoryChatPreferenceStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ChatPreferences] = {}
        self._lock = Lock()

    def get(self, tenant_id: str, owner_id: str) -> ChatPreferences:
        with self._lock:
            return self._rows.get((tenant_id, owner_id), ChatPreferences())

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, plain_diffs: bool, hidden_models: tuple[str, ...],
        default_memory_mode: str | _Unset = UNSET,
        collapse_message_input: bool | _Unset = UNSET,
        pin_latest_prompt: bool | _Unset = UNSET,
    ) -> ChatPreferences:
        with self._lock:
            current = self._rows.get((tenant_id, owner_id), ChatPreferences())
            if current.revision != expected_revision:
                raise StaleChatPreferences("stale chat preferences")
            result = ChatPreferences(
                plain_diffs=plain_diffs, hidden_models=hidden_models,
                theme=current.theme, terminal_font_size=current.terminal_font_size,
                terminal_shell=current.terminal_shell,
                terminal_completion_enabled=current.terminal_completion_enabled,
                density=current.density, language=current.language,
                shortcuts=current.shortcuts,
                default_memory_mode=(
                    current.default_memory_mode if isinstance(default_memory_mode, _Unset)
                    else default_memory_mode),
                collapse_message_input=(
                    current.collapse_message_input if isinstance(collapse_message_input, _Unset)
                    else collapse_message_input),
                pin_latest_prompt=(
                    current.pin_latest_prompt if isinstance(pin_latest_prompt, _Unset)
                    else pin_latest_prompt),
                revision=current.revision + 1,
            )
            self._rows[(tenant_id, owner_id)] = result
            return result

    def update_display(
        self, tenant_id: str, owner_id: str, expected_revision: int,
        *, theme: str, terminal_font_size: int,
        terminal_shell: str | None | _Unset = UNSET,
        terminal_completion_enabled: bool | _Unset = UNSET,
        density: str | _Unset = UNSET,
        language: str | _Unset = UNSET,
        shortcuts: dict[str, str] | _Unset = UNSET,
    ) -> ChatPreferences:
        with self._lock:
            current = self._rows.get((tenant_id, owner_id), ChatPreferences())
            if current.revision != expected_revision:
                raise StaleChatPreferences("stale chat preferences")
            result = ChatPreferences(
                plain_diffs=current.plain_diffs, hidden_models=current.hidden_models,
                theme=theme, terminal_font_size=terminal_font_size,
                terminal_shell=(
                    current.terminal_shell if isinstance(terminal_shell, _Unset)
                    else terminal_shell),
                terminal_completion_enabled=(
                    current.terminal_completion_enabled
                    if isinstance(terminal_completion_enabled, _Unset)
                    else terminal_completion_enabled),
                density=current.density if isinstance(density, _Unset) else density,
                language=current.language if isinstance(language, _Unset) else language,
                shortcuts=current.shortcuts if isinstance(shortcuts, _Unset) else shortcuts,
                default_memory_mode=current.default_memory_mode,
                collapse_message_input=current.collapse_message_input,
                pin_latest_prompt=current.pin_latest_prompt,
                revision=current.revision + 1,
            )
            self._rows[(tenant_id, owner_id)] = result
            return result


__all__ = [
    "ChatPreferences", "ChatPreferenceStore", "InMemoryChatPreferenceStore",
    "StaleChatPreferences",
]
