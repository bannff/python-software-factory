"""Typed MCP boundary for owner-scoped chat preferences."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_envelope, ok, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.chat_preferences import (
    UNSET, ChatPreferenceStore, ChatPreferences, StaleChatPreferences,
)


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    pass


class ChatPreferencesOutput(DTO):
    plain_diffs: bool
    hidden_models: tuple[str, ...] = Field(max_length=64)
    default_memory_mode: str
    collapse_message_input: bool
    pin_latest_prompt: bool
    revision: int = Field(ge=0)


class UpdateChatPreferencesInput(DTO):
    plain_diffs: bool
    hidden_models: list[str] = Field(max_length=64)
    default_memory_mode: str | None = Field(
        default=None, pattern=r"^(persistent|incognito|temporary)$",
    )
    collapse_message_input: bool | None = None
    pin_latest_prompt: bool | None = None
    expected_revision: int = Field(ge=0)

    @field_validator("hidden_models")
    @classmethod
    def _valid_models(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("hidden models must be unique")
        if any(not item.strip() or len(item) > 256 or "\x00" in item for item in value):
            raise ValueError("invalid hidden model id")
        return value


def _authority() -> tuple[str, str]:
    envelope = get_envelope()
    tenant = envelope.get("tenant_id") if isinstance(envelope, dict) else None
    owner = envelope.get("principal_id") if isinstance(envelope, dict) else None
    if not isinstance(tenant, str) or not tenant or len(tenant) > 256 \
            or not isinstance(owner, str) or not owner or len(owner) > 256:
        raise ValueError("chat_preferences_unavailable")
    return tenant, owner


def _output(value: ChatPreferences) -> ChatPreferencesOutput:
    return ChatPreferencesOutput(
        plain_diffs=value.plain_diffs, hidden_models=value.hidden_models,
        default_memory_mode=value.default_memory_mode,
        collapse_message_input=value.collapse_message_input,
        pin_latest_prompt=value.pin_latest_prompt, revision=value.revision,
    )

def register(mcp: Any, store: ChatPreferenceStore) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ChatPreferencesOutput)
    def ui_get_chat_preferences() -> ToolResult[ChatPreferencesOutput]:
        try:
            return ok(_output(store.get(*_authority())))
        except (OSError, ValueError):
            return fail("chat_preferences_unavailable")

    @typed_tool(mcp)
    @operational(input_model=UpdateChatPreferencesInput, output_model=ChatPreferencesOutput)
    def ui_update_chat_preferences(
        plain_diffs: bool, hidden_models: list[str], expected_revision: int,
        default_memory_mode: str | None = None, collapse_message_input: bool | None = None,
        pin_latest_prompt: bool | None = None,
    ) -> ToolResult[ChatPreferencesOutput]:
        """``default_memory_mode``/``collapse_message_input`` are OMITTED
        (``None``), not defaulted, when the caller doesn't pass them —
        every existing FE caller updates only the fields its own panel
        owns (plain_diffs/hidden_models here), so a bare default would
        silently reset the OTHER field back to its class default on
        every unrelated save (a real bug found and fixed alongside row
        12 — this tool's own prior signature had exactly that shape)."""
        try:
            tenant, owner = _authority()
            return ok(_output(store.update(
                tenant, owner, expected_revision,
                plain_diffs=plain_diffs, hidden_models=tuple(hidden_models),
                default_memory_mode=UNSET if default_memory_mode is None else default_memory_mode,
                collapse_message_input=UNSET if collapse_message_input is None else collapse_message_input,
                pin_latest_prompt=UNSET if pin_latest_prompt is None else pin_latest_prompt,
            )))
        except StaleChatPreferences:
            return fail("chat_preferences_conflict")
        except (OSError, ValueError):
            return fail("chat_preferences_unavailable")


__all__ = [
    "ChatPreferencesOutput", "EmptyInput", "UpdateChatPreferencesInput", "register",
]
