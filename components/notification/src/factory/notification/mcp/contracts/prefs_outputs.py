"""Typed owner notification preference egress."""
from __future__ import annotations

from pydantic import Field

from .inputs import NotificationDTO
from ...runtime.inbox_models import Priority
from ...runtime.prefs_models import MAX_PREFERENCE_KINDS, NotificationPreferences


class PreferencesOutput(NotificationDTO):
    global_muted: bool
    muted_kinds: list[str] = Field(max_length=MAX_PREFERENCE_KINDS)
    priority_overrides: dict[str, Priority]
    revision: int = Field(ge=1)

    @classmethod
    def from_preferences(
        cls, preferences: NotificationPreferences,
    ) -> "PreferencesOutput":
        return cls(
            global_muted=preferences.global_muted,
            muted_kinds=sorted(preferences.muted_kinds),
            priority_overrides=preferences.priority_overrides,
            revision=preferences.revision,
        )


__all__ = ["PreferencesOutput"]
