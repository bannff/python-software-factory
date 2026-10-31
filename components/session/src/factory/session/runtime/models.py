"""Strict domain models for persistent sessions and live steering."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
Identity = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")]
BoundedText = Annotated[str, Field(min_length=1, max_length=32_768)]
# Backward-compatible binding fields: empty string means "unmaterialized".
CrewRef = Annotated[str, Field(max_length=128, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,127}$")]
MemoryScope = Annotated[str, Field(max_length=64, pattern=r"^$|^[a-z0-9][a-z0-9_-]{0,63}$")]
SessionTag = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")]
# Row 3 (feature-map): Persistent/Incognito/Temporary. Empty string means
# "no explicit choice was made" — the caller resolves the owner's configured
# default before creating the session; a materialized session always carries
# one of the three real values once ``resolve_memory_mode`` has run.
MemoryMode = Annotated[str, Field(max_length=16, pattern=r"^$|^(persistent|incognito|temporary)$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SteerState(StrEnum):
    WRITTEN = "written"
    CONSUMED = "consumed"
    REQUEUED = "requeued"


class SessionRecord(StrictModel):
    tenant_id: Identity
    owner_id: Identity
    session_id: Identifier
    thread_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=200)]
    agent_id: Identifier
    model: Annotated[str, Field(min_length=1, max_length=256)]
    mode: MemoryMode = ""
    workspace: Annotated[str, Field(max_length=512)] = ""
    project: Annotated[str, Field(max_length=512)] = ""
    origin: Annotated[str, Field(max_length=64)] = "user"
    crew_id: CrewRef = ""
    memory_scope: MemoryScope = ""
    pinned_rank: float | None = Field(default=None, allow_inf_nan=False)
    unread: bool = False
    tags: tuple[SessionTag, ...] = Field(default=(), max_length=8)
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    # Row 16 (feature-map): the checkpoint id a regenerate/variant switch
    # last pinned as "current" for this thread. ``None`` means no branch
    # has ever been created — an ordinary turn resumes from LangGraph's
    # own latest checkpoint exactly as it always has. Once set, every
    # invocation (not just regenerate calls) must pass this explicit id,
    # because ``AsyncSqliteSaver``'s own "no id -> latest" fallback sorts
    # by checkpoint UUID, which is NOT necessarily the branch the owner is
    # viewing once a sibling branch exists (verified empirically against
    # the real installed LangGraph library before this field was added).
    active_checkpoint_id: Annotated[str, Field(max_length=128)] | None = None
    # Row 9 (feature-map): pinned message ids for this session's "Pinned
    # messages" panel. Bounded like ``tags`` (a small owner-curated set,
    # not an unbounded archive) — LangChain message ids are opaque UUIDs,
    # so no format pattern beyond a length bound is enforced.
    pinned_message_ids: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...] = Field(
        default=(), max_length=32,
    )
    # Row 18 (feature-map): the session's rolling conversation summary,
    # shown in its Summary surface. Empty until first generated;
    # regenerated on demand from the transcript excerpt the caller
    # supplies (this brick stays free of chat-transcript knowledge, the
    # same division of labor ``session_generate_title`` already follows) —
    # never auto-rewritten on every turn.
    summary: Annotated[str, Field(max_length=8_000)] = ""
    # Row 6 (feature-map): the user-defined folder this session is filed
    # under (empty = unfiled). A single owner-typed grouping label; unlike
    # ``tags`` it is one value, so it is stored as a plain column, not a
    # delimited list.
    folder: Annotated[str, Field(max_length=64, pattern=r"^[^\x00-\x1f\x7f]*$")] = ""
    revision: int = Field(ge=1)


class SteerMessage(StrictModel):
    tenant_id: Identity
    owner_id: Identity
    session_id: Identifier
    delivery_id: Identifier
    send_id: Identifier
    content: BoundedText
    state: SteerState
    created_at: datetime
    consumed_at: datetime | None = None
    requeued_at: datetime | None = None
    revision: int = Field(ge=1)


class CompletionState(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"


class CompletionOutcome(StrEnum):
    OK = "ok"
    FAILED = "failed"
    STOPPED = "stopped"
    INTERRUPTED = "interrupted"


class CompletionDelivery(StrictModel):
    tenant_id: Identity
    owner_id: Identity
    session_id: Identifier
    run_id: Identity
    outcome: CompletionOutcome
    summary: BoundedText
    result_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    state: CompletionState
    created_at: datetime
    delivered_at: datetime | None = None
    revision: int = Field(ge=1)


__all__ = [
    "CompletionDelivery", "CompletionOutcome", "CompletionState", "CrewRef",
    "MemoryMode", "MemoryScope", "SessionRecord", "SessionTag", "SteerMessage", "SteerState",
]
