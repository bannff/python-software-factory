"""Strict ingress DTOs for owner-scoped notification preferences."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .inputs import NotificationDTO
from ...runtime.inbox_models import _NAME_RE
from ...runtime.prefs_models import MAX_PREFERENCE_KINDS

PreferencePriority = Literal["passive", "default", "critical"]


class PreferencesGetInput(NotificationDTO):
    pass


class PreferencesUpdateInput(NotificationDTO):
    global_muted: bool
    muted_kinds: list[str] = Field(max_length=MAX_PREFERENCE_KINDS)
    priority_overrides: dict[str, PreferencePriority]
    expected_revision: int = Field(ge=1)

    @field_validator("muted_kinds")
    @classmethod
    def _validate_muted(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(
            not _NAME_RE.fullmatch(kind) for kind in value
        ):
            raise ValueError("invalid notification preference kind")
        return value

    @field_validator("priority_overrides")
    @classmethod
    def _validate_overrides(
        cls, value: dict[str, PreferencePriority],
    ) -> dict[str, PreferencePriority]:
        if len(value) > MAX_PREFERENCE_KINDS or any(
            not _NAME_RE.fullmatch(kind) for kind in value
        ):
            raise ValueError("invalid notification priority override")
        return value


__all__ = [
    "PreferencePriority", "PreferencesGetInput", "PreferencesUpdateInput",
]
