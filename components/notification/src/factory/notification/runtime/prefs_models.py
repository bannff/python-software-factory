"""Owner-scoped notification delivery preferences.

Preferences bind to durable inbox ``kind`` values, not secret-bearing workspace
channel configuration. Overrides affect best-effort delivery only; inbox records
remain immutable so producer dedupe identity is stable across preference changes.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .inbox_models import Priority, _NAME_RE
from .inbox_targets import Identity

MAX_PREFERENCE_KINDS = 128


class NotificationPreferences(BaseModel):
    """Strict owner preference snapshot guarded by revision CAS."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: Identity
    owner_id: Identity
    global_muted: bool = False
    muted_kinds: frozenset[str] = Field(default_factory=frozenset)
    priority_overrides: dict[str, Priority] = Field(default_factory=dict)
    revision: Annotated[int, Field(ge=1)] = 1

    @field_validator("muted_kinds")
    @classmethod
    def _validate_muted_kinds(cls, value: frozenset[str]) -> frozenset[str]:
        if len(value) > MAX_PREFERENCE_KINDS or any(
            not _NAME_RE.fullmatch(kind) for kind in value
        ):
            raise ValueError("invalid notification preference kind")
        return value

    @field_validator("priority_overrides")
    @classmethod
    def _validate_overrides(cls, value: dict[str, Priority]) -> dict[str, Priority]:
        if len(value) > MAX_PREFERENCE_KINDS or any(
            not _NAME_RE.fullmatch(kind) for kind in value
        ):
            raise ValueError("invalid notification priority override")
        return value

    def effective_delivery(
        self, kind: str, base_priority: Priority
    ) -> tuple[bool, Priority]:
        """Return delivery permission and effective delivery-only priority."""
        deliver = not self.global_muted and kind not in self.muted_kinds
        return deliver, self.priority_overrides.get(kind, base_priority)


__all__ = ["MAX_PREFERENCE_KINDS", "NotificationPreferences"]
