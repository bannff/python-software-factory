"""Concrete Pydantic v2 egress DTOs for the durable notification inbox.

Each wrapper embeds the strict frozen :class:`NotificationRecord` verbatim so
the public surface returns the exact durable truth (redacted at construction,
owner-scoped by identity) without a lossy re-projection.
"""
from __future__ import annotations

from ..contracts.inputs import NotificationDTO
from ...runtime.inbox_models import NotificationRecord


class InboxNotificationOutput(NotificationDTO):
    notification: NotificationRecord


class InboxListOutput(NotificationDTO):
    notifications: list[NotificationRecord]
    count: int


class InboxMarkAllReadOutput(NotificationDTO):
    marked_count: int


__all__ = [
    "InboxListOutput", "InboxMarkAllReadOutput", "InboxNotificationOutput",
]
