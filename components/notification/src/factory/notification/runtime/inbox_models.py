"""Strict frozen owner-scoped inbox record, results, and content-free errors.

``NotificationRecord`` is the durable inbox truth persisted before best-effort
channel delivery. ``title``/``body`` are redacted at construction (the single
guarantee point), so persistence can never hold an unredacted value. Content
identity for idempotent dedupe excludes volatile fields (id, timestamps,
revision) so a replayed producer event collapses onto the first stored row.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .inbox_redact import MAX_BODY_CHARS, MAX_TITLE_CHARS, redact
from .inbox_targets import Identity, NotificationTarget, target_id, target_kind

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")            # kind
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:=+-]{0,255}$")  # id, dedupe_key


class Priority(str, Enum):
    """Inbox notification priority. No other tiers exist."""

    PASSIVE = "passive"
    DEFAULT = "default"
    CRITICAL = "critical"


class InboxCommitStatus(str, Enum):
    """Result of an idempotent create-or-replay write."""

    CREATED = "created"    # first write of this dedupe identity
    REPLAYED = "replayed"  # identical content already stored (no-op)
    CONFLICT = "conflict"  # dedupe key exists with different content (no overwrite)


class NotificationRecord(BaseModel):
    """Frozen durable inbox record. Owner-scoped and dedupe-idempotent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: Identity
    owner_id: Identity
    notification_id: str
    kind: str
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARS)
    body: str = Field(default="", max_length=MAX_BODY_CHARS)
    priority: Priority = Priority.DEFAULT
    target: NotificationTarget
    dedupe_key: str
    created_at: datetime
    read_at: datetime | None = None
    revision: Annotated[int, Field(ge=1)] = 1

    @field_validator("notification_id", "dedupe_key")
    @classmethod
    def _v_token(cls, v: str) -> str:
        if not _TOKEN_RE.fullmatch(v):
            raise ValueError("NotificationRecord identifier is invalid")
        return v

    @field_validator("kind")
    @classmethod
    def _v_kind(cls, v: str) -> str:
        if not _NAME_RE.fullmatch(v):
            raise ValueError("NotificationRecord.kind is invalid")
        return v

    @field_validator("created_at", "read_at")
    @classmethod
    def _v_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("NotificationRecord timestamp must be timezone-aware")
        return value.astimezone(timezone.utc) if value is not None else None

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return redact(v, limit=MAX_TITLE_CHARS)

    @field_validator("body")
    @classmethod
    def _v_body(cls, v: str) -> str:
        return redact(v, limit=MAX_BODY_CHARS)

    @property
    def content_digest(self) -> str:
        """Digest over redacted content — excludes id/timestamps/revision."""
        material = {
            "kind": self.kind, "title": self.title, "body": self.body,
            "priority": self.priority.value,
            "target_kind": target_kind(self.target), "target_id": target_id(self.target),
            "dedupe_key": self.dedupe_key,
        }
        canonical = json.dumps(material, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InboxCommit(BaseModel):
    """Outcome of an idempotent ``create_or_replay`` call."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: InboxCommitStatus
    record: NotificationRecord


class InboxAdapterError(RuntimeError):
    """Base for content-free inbox adapter failures. Never carries source text."""


class NotificationNotFoundError(InboxAdapterError):
    """Opaque not-found for a foreign or absent owner-scoped notification."""

    def __init__(self) -> None:
        super().__init__("notification not found")


class RevisionConflictError(InboxAdapterError):
    """Optimistic-concurrency failure on a revision-fenced mark write."""

    def __init__(self) -> None:
        super().__init__("notification revision is stale")


class UnreadCountConflictError(InboxAdapterError):
    """Count-fence failure on mark-all-read: observed unread count drifted.

    Raised when ``expected_unread_count`` did not match the live unread count.
    The fenced statement mutated zero rows, so no partial mark occurred.
    """

    def __init__(self) -> None:
        super().__init__("notification unread count is stale")


__all__ = [
    "InboxAdapterError", "InboxCommit", "InboxCommitStatus",
    "NotificationNotFoundError", "NotificationRecord", "Priority",
    "RevisionConflictError", "UnreadCountConflictError",
]
