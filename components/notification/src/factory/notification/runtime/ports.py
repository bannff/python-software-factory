"""Notification ports - Protocol interfaces for notification backends.

Defines abstract interfaces that notification backends must implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .inbox_models import InboxCommit, NotificationRecord
from .prefs_models import NotificationPreferences
from .models import NotificationRequest, DeliveryStatus


@dataclass
class BackendHealth:
    """Health status for a notification backend."""

    healthy: bool
    backend: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class NotificationPort(Protocol):
    """Port: Notification delivery backend (local, Celery, etc.)"""

    @property
    def name(self) -> str:
        """Unique name of the backend."""
        ...

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the backend with configuration."""
        ...

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        """Dispatch a notification."""
        ...

    async def health_check(self) -> bool:
        """Return True if backend is healthy."""
        ...


@runtime_checkable
class ChannelPort(Protocol):
    """Port: Notification channel (email, SMS, push, etc.)"""

    @property
    def channel_type(self) -> str:
        """Type identifier for this channel."""
        ...

    async def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        """Send a message through this channel."""
        ...

    async def validate_recipient(self, recipient: str) -> bool:
        """Validate recipient address format."""
        ...


@runtime_checkable
class InboxStore(Protocol):
    """Port: durable owner-scoped notification inbox truth.

    Distinct from ``NotificationPort`` (delivery). Persists inbox records
    before best-effort channel delivery; owner-scoped reads are opaque and a
    foreign/absent id is not-found. Mark writes are revision-fenced.
    """

    def initialize(self) -> None:
        """Create backing schema if absent (idempotent)."""
        ...

    def create_or_replay(self, record: NotificationRecord) -> InboxCommit:
        """Persist a record idempotently by ``(tenant, owner, dedupe_key)``."""
        ...

    def get(
        self, tenant_id: str, owner_id: str, notification_id: str
    ) -> NotificationRecord | None:
        """Return an owner-scoped record, or ``None`` (opaque) if foreign/absent."""
        ...

    def list(
        self, tenant_id: str, owner_id: str, *, limit: int, offset: int = 0,
        unread_only: bool = False,
    ) -> list[NotificationRecord]:
        """List owner-scoped records newest-first with bounded paging."""
        ...

    def mark_read(
        self, tenant_id: str, owner_id: str, notification_id: str, *,
        expected_revision: int, read_at: datetime,
    ) -> NotificationRecord:
        """Revision-CAS mark a record read. Raises on stale/foreign."""
        ...

    def mark_unread(
        self, tenant_id: str, owner_id: str, notification_id: str, *,
        expected_revision: int,
    ) -> NotificationRecord:
        """Revision-CAS mark a record unread. Raises on stale/foreign."""
        ...

    def mark_all_read(
        self, tenant_id: str, owner_id: str, *,
        expected_unread_count: int, read_at: datetime,
    ) -> int:
        """Count-fenced mark-all-read. Update only when the live unread count
        equals ``expected_unread_count``; on mismatch mutate zero rows and
        raise. Returns the number of records transitioned to read."""
        ...


@runtime_checkable
class PreferencesStore(Protocol):
    """Port: durable owner-scoped delivery preferences with revision CAS."""

    def initialize(self) -> None:
        """Create backing schema if absent (idempotent)."""
        ...

    def get(self, tenant_id: str, owner_id: str) -> NotificationPreferences:
        """Return the saved snapshot or an unsaved revision-one default."""
        ...

    def put(
        self, preferences: NotificationPreferences, *, expected_revision: int
    ) -> NotificationPreferences:
        """Replace preferences iff the live revision matches the fence."""
        ...
