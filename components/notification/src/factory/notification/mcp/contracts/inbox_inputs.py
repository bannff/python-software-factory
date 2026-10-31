"""Strict Pydantic v2 ingress DTOs for the durable notification inbox.

All inbox tools derive tenant/owner from the ambient request envelope, never
from input — so no identity field appears here. Bounds mirror the store
contract (``1 <= limit <= 100``) and the canonical id/token alphabet.
"""
from __future__ import annotations

from pydantic import Field

from .inputs import NotificationDTO

# Canonical notification id — mirrors ``inbox_models._TOKEN_RE``.
NOTIFICATION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:=+-]{0,255}$"


class InboxListInput(NotificationDTO):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    unread_only: bool = False


class InboxGetInput(NotificationDTO):
    notification_id: str = Field(pattern=NOTIFICATION_ID_PATTERN)


class InboxMarkReadInput(NotificationDTO):
    notification_id: str = Field(pattern=NOTIFICATION_ID_PATTERN)
    expected_revision: int = Field(ge=1)


class InboxMarkAllReadInput(NotificationDTO):
    expected_unread_count: int = Field(ge=0)


__all__ = [
    "InboxGetInput", "InboxListInput", "InboxMarkAllReadInput", "InboxMarkReadInput",
    "NOTIFICATION_ID_PATTERN",
]
