"""Strict DTOs for session lifecycle and steering MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from ..runtime.models import Identifier, SessionRecord, SessionTag, SteerMessage
from .contracts import InputDTO, OutputDTO


class EnvelopeInput(InputDTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    timestamp: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SessionRefInput(InputDTO):
    session_id: Identifier
    envelope: EnvelopeInput | None = None


class ThreadRefInput(InputDTO):
    thread_id: Identifier
    envelope: EnvelopeInput | None = None


class ListSessionsInput(InputDTO):
    include_archived: bool = False
    envelope: EnvelopeInput | None = None


class EnvelopeOnlyInput(InputDTO):
    """Owner-scoped, no other args — the shape row 8's bulk "Delete all"
    preview count and clear-all tools need (matches upstream's own
    ``GET /api/sessions/clearable/count`` / ``DELETE /api/sessions``, which
    take no per-row identifiers)."""
    envelope: EnvelopeInput | None = None


class CreateSessionInput(InputDTO):
    title: str = Field(min_length=1, max_length=200)
    agent_id: Identifier
    model: str = Field(min_length=1, max_length=256)
    mode: str = Field(default="", max_length=16, pattern=r"^$|^(persistent|incognito|temporary)$")
    workspace: str = Field(default="", max_length=512)
    project: str = Field(default="", max_length=512)
    origin: str = Field(default="user", max_length=64)
    crew_id: str = Field(default="", max_length=128, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,127}$")
    memory_scope: str = Field(default="", max_length=64, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,63}$")
    envelope: EnvelopeInput | None = None


class EnsureThreadInput(InputDTO):
    thread_id: Identifier
    title: str = Field(min_length=1, max_length=200)
    agent_id: Identifier
    model: str = Field(min_length=1, max_length=256)
    mode: str = Field(default="", max_length=16, pattern=r"^$|^(persistent|incognito|temporary)$")
    crew_id: str = Field(default="", max_length=128, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,127}$")
    memory_scope: str = Field(default="", max_length=64, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,63}$")
    project: str = Field(default="", max_length=512)
    envelope: EnvelopeInput | None = None


class RenameSessionInput(SessionRefInput):
    title: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)


class GenerateTitleInput(SessionRefInput):
    excerpt: str = Field(min_length=1, max_length=8_000)
    expected_revision: int = Field(ge=1)


class BindProjectInput(SessionRefInput):
    project: str = Field(min_length=1, max_length=512)
    expected_revision: int = Field(ge=1)


class SetModelInput(SessionRefInput):
    model: str = Field(min_length=1, max_length=256)
    expected_revision: int = Field(ge=1)


class SetActiveCheckpointInput(SessionRefInput):
    checkpoint_id: str | None = Field(default=None, max_length=128)
    expected_revision: int = Field(ge=1)


class RebindSessionInput(SessionRefInput):
    agent_id: Identifier
    model: str = Field(min_length=1, max_length=256)
    expected_revision: int = Field(ge=1)
    project: str | None = Field(default=None, min_length=1, max_length=512)
    workspace: str | None = Field(default=None, max_length=512)
    crew_id: str = Field(default="", max_length=128, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,127}$")
    memory_scope: str = Field(default="", max_length=64, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,63}$")


class RevisionSessionInput(SessionRefInput):
    expected_revision: int = Field(ge=1)


class DeleteOutput(OutputDTO):
    session_id: str
    deleted: bool


class ClearableCountOutput(OutputDTO):
    count: int


class ClearArchivedOutput(OutputDTO):
    deleted_count: int


class StopOutput(OutputDTO):
    session_id: str
    cancelled: bool


class SetPinnedInput(RevisionSessionInput):
    pinned: bool


class SetTagsInput(RevisionSessionInput):
    tags: tuple[SessionTag, ...] = Field(max_length=8)

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("session tags must be unique")
        return value


class MovePinnedInput(RevisionSessionInput):
    before_session_id: Identifier | None = None


class SteerInput(SessionRefInput):
    send_id: Identifier
    content: str = Field(min_length=1, max_length=32_768)


class GetSteerInput(SessionRefInput):
    delivery_id: Identifier


class AcknowledgeSteerInput(InputDTO):
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    session_id: Identifier
    delivery_id: Identifier
    revision: int = Field(ge=1)


class SessionOutput(OutputDTO):
    session: SessionRecord


class SessionsOutput(OutputDTO):
    sessions: list[SessionRecord]


class SteerOutput(OutputDTO):
    steer: SteerMessage


class SteersOutput(OutputDTO):
    steers: list[SteerMessage]


__all__ = [
    "AcknowledgeSteerInput", "BindProjectInput", "ClearArchivedOutput", "ClearableCountOutput",
    "CreateSessionInput", "DeleteOutput", "EnsureThreadInput", "EnvelopeOnlyInput", "GetSteerInput",
    "GenerateTitleInput", "ListSessionsInput", "MovePinnedInput", "RebindSessionInput", "RenameSessionInput", "RevisionSessionInput",
    "SessionOutput", "SessionRefInput", "SessionsOutput", "SetModelInput", "SetPinnedInput", "SetTagsInput", "SteerInput", "SteerOutput",
    "SteersOutput", "StopOutput", "ThreadRefInput",
]
