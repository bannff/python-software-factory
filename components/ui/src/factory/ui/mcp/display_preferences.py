"""Typed MCP boundary for owner-scoped Display preferences."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_envelope, ok, operational
from factory.mcp_utils.registration import typed_tool
from ..runtime.chat_preferences import ChatPreferenceStore, StaleChatPreferences

class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class EmptyInput(DTO):
    pass

_LANGUAGE = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"


class DisplayPreferencesOutput(DTO):
    theme: Literal["system", "dark", "light"]
    terminal_font_size: int = Field(ge=10, le=18)
    terminal_shell: str | None = Field(default=None, max_length=512)
    terminal_completion_enabled: bool
    density: Literal["comfortable", "compact"]
    language: str = Field(min_length=2, max_length=35, pattern=_LANGUAGE)
    shortcuts: dict[str, str] = Field(max_length=32)
    revision: int = Field(ge=0)

class UpdateDisplayPreferencesInput(DTO):
    """Atomic revisioned replacement of the complete Display preference object."""

    theme: Literal["system", "dark", "light"]
    terminal_font_size: int = Field(ge=10, le=18)
    terminal_shell: str | None = Field(max_length=512)
    terminal_completion_enabled: bool
    density: Literal["comfortable", "compact"]
    language: str = Field(min_length=2, max_length=35, pattern=_LANGUAGE)
    shortcuts: dict[str, str] = Field(max_length=32)
    expected_revision: int = Field(ge=0)

def _authority() -> tuple[str, str]:
    value = get_envelope()
    tenant = value.get("tenant_id") if isinstance(value, dict) else None
    owner = value.get("principal_id") if isinstance(value, dict) else None
    if not isinstance(tenant, str) or not tenant or not isinstance(owner, str) or not owner:
        raise ValueError("display_preferences_unavailable")
    return tenant, owner

def _output(value: Any) -> DisplayPreferencesOutput:
    return DisplayPreferencesOutput(
        theme=value.theme, terminal_font_size=value.terminal_font_size,
        terminal_shell=value.terminal_shell,
        terminal_completion_enabled=value.terminal_completion_enabled,
        density=value.density, language=value.language, shortcuts=dict(value.shortcuts),
        revision=value.revision,
    )

def register(mcp: Any, store: ChatPreferenceStore) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=DisplayPreferencesOutput)
    def ui_get_display_preferences() -> ToolResult[DisplayPreferencesOutput]:
        try:
            return ok(_output(store.get(*_authority())))
        except (OSError, ValueError):
            return fail("display_preferences_unavailable")

    @typed_tool(mcp)
    @operational(input_model=UpdateDisplayPreferencesInput, output_model=DisplayPreferencesOutput)
    def ui_update_display_preferences(
        theme: str, terminal_font_size: int, expected_revision: int,
        terminal_shell: str | None, terminal_completion_enabled: bool,
        density: str, language: str, shortcuts: dict[str, str],
    ) -> ToolResult[DisplayPreferencesOutput]:
        try:
            tenant, owner = _authority()
            return ok(_output(store.update_display(
                tenant, owner, expected_revision, theme=theme,
                terminal_font_size=terminal_font_size, terminal_shell=terminal_shell,
                terminal_completion_enabled=terminal_completion_enabled,
                density=density, language=language, shortcuts=shortcuts,
            )))
        except StaleChatPreferences:
            return fail("display_preferences_conflict")
        except (OSError, ValueError):
            return fail("display_preferences_unavailable")

__all__ = ["DisplayPreferencesOutput", "UpdateDisplayPreferencesInput", "register"]
