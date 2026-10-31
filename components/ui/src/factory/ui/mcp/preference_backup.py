"""Row 102 (feature-map) — typed MCP boundary for preference backup/restore.

Deliberately its own file (not added to ``chat_preferences.py`` /
``display_preferences.py``, both already near the 200 LOC ceiling): a
thin composition over ``preference_backup.py``'s two functions, which
themselves compose the EXISTING ``ChatPreferenceStore`` calls.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_envelope, ok, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.chat_preferences import ChatPreferenceStore, ChatPreferences, StaleChatPreferences
from ..runtime.preference_backup import export_preferences, restore_preferences


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    pass


class PreferenceBackupOutput(DTO):
    """A complete, restorable snapshot of one owner's durable UI preferences."""

    plain_diffs: bool
    hidden_models: tuple[str, ...] = Field(max_length=64)
    default_memory_mode: str
    theme: str
    terminal_font_size: int = Field(ge=10, le=18)
    terminal_shell: str | None = Field(default=None, max_length=512)
    terminal_completion_enabled: bool
    density: str
    language: str = Field(min_length=2, max_length=35)
    shortcuts: dict[str, str] = Field(max_length=32)
    collapse_message_input: bool = False
    pin_latest_prompt: bool = False
    revision: int = Field(ge=0)


class RestorePreferencesInput(PreferenceBackupOutput):
    """Same shape as the export — a snapshot to write back verbatim.
    ``revision`` is accepted for round-trip fidelity but IGNORED on
    restore (see ``restore_preferences``'s own docstring: a restore
    always CAS-fences against the CURRENT record, never the snapshot's
    original revision)."""

    @field_validator("hidden_models")
    @classmethod
    def _valid_models(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("hidden models must be unique")
        return value


def _authority() -> tuple[str, str]:
    envelope = get_envelope()
    tenant = envelope.get("tenant_id") if isinstance(envelope, dict) else None
    owner = envelope.get("principal_id") if isinstance(envelope, dict) else None
    if not isinstance(tenant, str) or not tenant or len(tenant) > 256 \
            or not isinstance(owner, str) or not owner or len(owner) > 256:
        raise ValueError("preference_backup_unavailable")
    return tenant, owner


def _output(value: ChatPreferences) -> PreferenceBackupOutput:
    return PreferenceBackupOutput(
        plain_diffs=value.plain_diffs, hidden_models=value.hidden_models,
        default_memory_mode=value.default_memory_mode, theme=value.theme,
        terminal_font_size=value.terminal_font_size, terminal_shell=value.terminal_shell,
        terminal_completion_enabled=value.terminal_completion_enabled,
        density=value.density, language=value.language, shortcuts=dict(value.shortcuts),
        collapse_message_input=value.collapse_message_input,
        pin_latest_prompt=value.pin_latest_prompt, revision=value.revision,
    )


def register(mcp: Any, store: ChatPreferenceStore) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=PreferenceBackupOutput)
    def ui_export_preferences() -> ToolResult[PreferenceBackupOutput]:
        try:
            return ok(_output(export_preferences(store, *_authority())))
        except (OSError, ValueError):
            return fail("preference_backup_unavailable")

    @typed_tool(mcp)
    @operational(input_model=RestorePreferencesInput, output_model=PreferenceBackupOutput)
    def ui_import_preferences(
        plain_diffs: bool, hidden_models: tuple[str, ...], default_memory_mode: str,
        theme: str, terminal_font_size: int, terminal_completion_enabled: bool,
        density: str, language: str, shortcuts: dict[str, str], revision: int,
        terminal_shell: str | None = None, collapse_message_input: bool = False,
        pin_latest_prompt: bool = False,
    ) -> ToolResult[PreferenceBackupOutput]:
        snapshot = ChatPreferences(
            plain_diffs=plain_diffs, hidden_models=hidden_models,
            default_memory_mode=default_memory_mode, theme=theme,
            terminal_font_size=terminal_font_size, terminal_shell=terminal_shell,
            terminal_completion_enabled=terminal_completion_enabled,
            density=density, language=language, shortcuts=shortcuts,
            collapse_message_input=collapse_message_input,
            pin_latest_prompt=pin_latest_prompt, revision=revision,
        )
        try:
            tenant, owner = _authority()
            return ok(_output(restore_preferences(store, tenant, owner, snapshot)))
        except StaleChatPreferences:
            return fail("preference_backup_conflict")
        except (OSError, ValueError):
            return fail("preference_backup_unavailable")


__all__ = ["PreferenceBackupOutput", "RestorePreferencesInput", "register"]
