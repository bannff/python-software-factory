"""Strict DTO for the pinned-messages MCP tool (row 9, feature-map).

Split from ``lifecycle_contracts.py`` to keep that file under the
200 LOC ceiling — same doctrine as every other LOC-driven extraction
this session.
"""
from __future__ import annotations

from pydantic import Field, field_validator

from .lifecycle_contracts import RevisionSessionInput


class SetPinnedMessagesInput(RevisionSessionInput):
    """The session's complete pinned-message set, replaced atomically —
    same "whole-set CAS write" shape as ``SetTagsInput``."""

    pinned_message_ids: tuple[str, ...] = Field(max_length=32)

    @field_validator("pinned_message_ids")
    @classmethod
    def unique_pins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("pinned message ids must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("pinned message ids must not be blank")
        return value


__all__ = ["SetPinnedMessagesInput"]
