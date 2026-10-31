"""Strict ingress/egress for the trusted scheduler->inbox projection tool.

``inbox_publish`` is service-only (caller ``scheduler``, ``projection`` binding).
The six binding fields (tenant/owner/event_type/subject_id/revision/
payload_digest) are top-level so the native caller-binding rail can bind them;
this slice accepts a *schedule* target only, so the target id is ``subject_id``
and no free-form target/URL field exists. ``payload_digest`` cryptographically
binds content + dedupe key + target and is recomputed before any effect.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...runtime.inbox_redact import MAX_BODY_CHARS, MAX_TITLE_CHARS
from ...runtime.inbox_targets import CanonicalId
from .inputs import NotificationDTO

# The only source-event semantic this slice accepts.
SchedulerEventType = Literal["scheduler.schedule.auto_paused"]
DIGEST_PATTERN = r"^[0-9a-f]{64}$"
DEDUPE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:=+-]{0,255}$"
InboxPriority = Literal["passive", "default", "critical"]


class InboxPublishInput(NotificationDTO):
    """Trusted producer projection ingress; target is always a schedule."""

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    event_type: SchedulerEventType
    subject_id: CanonicalId            # the schedule id == target id
    revision: int = Field(ge=0)        # fire_sequence
    payload_digest: str = Field(pattern=DIGEST_PATTERN)
    dedupe_key: str = Field(pattern=DEDUPE_PATTERN)
    priority: InboxPriority = "critical"
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARS)
    body: str = Field(default="", max_length=MAX_BODY_CHARS)


class InboxPublishOutput(NotificationDTO):
    """Typed egress: persisted truth plus best-effort delivery status."""

    persisted: bool
    status: Literal["created", "replayed"]
    notification_id: str
    delivery: Literal["delivered", "skipped", "failed"]


__all__ = [
    "InboxPriority", "InboxPublishInput", "InboxPublishOutput",
    "SchedulerEventType",
]
